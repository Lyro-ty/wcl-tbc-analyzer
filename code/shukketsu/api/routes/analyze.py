import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from shukketsu.agent.utils import THINK_PATTERN
from shukketsu.agent.utils import strip_think_tags as _strip_think_tags

logger = logging.getLogger(__name__)

_MAX_THINK_BUFFER = 32768  # 32KB max for think-tag buffering


router = APIRouter(prefix="/api", tags=["analysis"])

# Graph instance, set during app startup
_compiled_graph = None

# Langfuse handler class, set during app startup (optional).
# Store the class, not an instance — create a fresh handler per request
# to avoid interleaved/corrupt trace data across concurrent requests.
_langfuse_handler_cls = None


def set_langfuse_handler(handler_or_cls) -> None:
    """Accept either a class (preferred) or an instance (legacy)."""
    global _langfuse_handler_cls
    if isinstance(handler_or_cls, type):
        _langfuse_handler_cls = handler_or_cls
    else:
        # Legacy: was passed an instance; extract its class
        _langfuse_handler_cls = type(handler_or_cls)


def _get_langfuse_handler():
    return _langfuse_handler_cls() if _langfuse_handler_cls else None


class AnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


# Limit concurrent LLM invocations
_llm_semaphore = asyncio.Semaphore(2)


class AnalyzeResponse(BaseModel):
    answer: str


def set_graph(graph) -> None:
    global _compiled_graph
    _compiled_graph = graph


def _get_graph():
    return _compiled_graph


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    graph = _get_graph()
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        async with _llm_semaphore:
            config = {}
            handler = _get_langfuse_handler()
            if handler:
                config["callbacks"] = [handler]
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=request.question)]},
                config=config,
            )
    except Exception as exc:
        logger.exception("Agent invocation failed")
        raise HTTPException(
            status_code=503, detail="Analysis service unavailable",
        ) from exc

    messages = result.get("messages", [])
    raw = messages[-1].content if messages else "No response generated."
    answer = _strip_think_tags(raw)

    return AnalyzeResponse(answer=answer)


@router.post("/analyze/stream")
async def analyze_stream(request: AnalyzeRequest):
    graph = _get_graph()
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    async def event_generator():
        buffer = ""
        think_done = False

        try:
            config = {}
            handler = _get_langfuse_handler()
            if handler:
                config["callbacks"] = [handler]
            async with _llm_semaphore:
                async for chunk, metadata in graph.astream(
                    {"messages": [HumanMessage(content=request.question)]},
                    stream_mode="messages",
                    config=config,
                ):
                    node = (
                        metadata.get("langgraph_node")
                        if isinstance(metadata, dict) else None
                    )

                    # Reset think-tag buffer between agent turns
                    if node == "tools":
                        buffer = ""
                        think_done = False
                        continue

                    if node != "agent":
                        continue

                    if not hasattr(chunk, "content") or not chunk.content:
                        continue

                    # Skip tool call chunks (intermediate turns)
                    if getattr(chunk, "tool_call_chunks", None):
                        continue

                    token = chunk.content

                    if not think_done:
                        buffer += token
                        if len(buffer) > _MAX_THINK_BUFFER:
                            cleaned = _strip_think_tags(buffer)
                            if cleaned.strip():
                                yield {
                                    "data": json.dumps(
                                        {"token": cleaned}
                                    )
                                }
                            buffer = ""
                            think_done = True
                            continue
                        if "</think>" in buffer:
                            after = THINK_PATTERN.sub("", buffer)
                            think_done = True
                            buffer = ""
                            if after.strip():
                                yield {"data": json.dumps({"token": after})}
                        continue

                    yield {"data": json.dumps({"token": token})}

                # If we buffered but never saw </think>, flush as content
                if buffer and not think_done:
                    cleaned = _strip_think_tags(buffer)
                    if cleaned.strip():
                        yield {"data": json.dumps({"token": cleaned})}

                yield {"data": json.dumps({"done": True})}

        except asyncio.CancelledError:
            logger.info(
                "Streaming analysis cancelled (client disconnect)"
            )
            return
        except Exception:
            logger.exception("Streaming analysis failed")
            yield {"event": "error", "data": json.dumps({"detail": "Analysis failed"})}

    return EventSourceResponse(event_generator())
