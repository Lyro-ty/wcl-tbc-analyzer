import logging
import re

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_THINK_PATTERN = re.compile(r"^.*?</think>\s*", flags=re.DOTALL)


def _strip_think_tags(text: str) -> str:
    """Strip Nemotron's leaked reasoning/think tags from output."""
    return _THINK_PATTERN.sub("", text)


router = APIRouter(prefix="/api", tags=["analysis"])

# Graph instance, set during app startup
_compiled_graph = None


class AnalyzeRequest(BaseModel):
    question: str


class AnalyzeResponse(BaseModel):
    answer: str
    query_type: str | None = None


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
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=request.question)]}
        )
    except Exception as exc:
        logger.exception("Agent invocation failed")
        raise HTTPException(
            status_code=503, detail="Analysis service unavailable",
        ) from exc

    messages = result.get("messages", [])
    raw = messages[-1].content if messages else "No response generated."
    answer = _strip_think_tags(raw)

    return AnalyzeResponse(
        answer=answer,
        query_type=result.get("query_type"),
    )
