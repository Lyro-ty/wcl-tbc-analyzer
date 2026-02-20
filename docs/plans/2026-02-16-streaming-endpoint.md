# Streaming Endpoint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add SSE streaming to the agent chat so users see the analysis token-by-token instead of a 30-120 second spinner wait.

**Architecture:** New `POST /api/analyze/stream` SSE endpoint using LangGraph `astream(stream_mode="messages")`, filtered to the `analyze` node. Think-tag buffering on the backend. Frontend uses `fetch()` + `ReadableStream` to parse SSE and incrementally update the chat message.

**Tech Stack:** FastAPI + sse_starlette (backend), fetch + ReadableStream (frontend), LangGraph astream

---

### Task 1: Add SSE streaming endpoint

**Files:**
- Modify: `code/shukketsu/api/routes/analyze.py`

**Implementation:**

Add the streaming endpoint after the existing `/analyze` POST:

```python
import json
from sse_starlette.sse import EventSourceResponse
from langchain_core.messages import AIMessageChunk, HumanMessage

@router.post("/analyze/stream")
async def analyze_stream(request: AnalyzeRequest):
    graph = _get_graph()
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    async def event_generator():
        buffer = ""
        think_done = False
        query_type = None

        try:
            async for chunk, metadata in graph.astream(
                {"messages": [HumanMessage(content=request.question)]},
                stream_mode="messages",
            ):
                # Track query_type from state
                if isinstance(metadata, dict):
                    qt = metadata.get("query_type")
                    if qt:
                        query_type = qt

                # Only stream tokens from the analyze node
                if not isinstance(metadata, dict) or metadata.get("langgraph_node") != "analyze":
                    continue

                if not hasattr(chunk, "content") or not chunk.content:
                    continue

                token = chunk.content

                if not think_done:
                    buffer += token
                    # Check if think block has ended
                    if "</think>" in buffer:
                        # Strip everything up to and including </think>
                        after = _THINK_PATTERN.sub("", buffer)
                        think_done = True
                        buffer = ""
                        if after.strip():
                            yield {"data": json.dumps({"token": after})}
                    continue

                yield {"data": json.dumps({"token": token})}

            # If we buffered but never saw </think>, flush the buffer as content
            if buffer and not think_done:
                cleaned = _strip_think_tags(buffer)
                if cleaned.strip():
                    yield {"data": json.dumps({"token": cleaned})}

            yield {"data": json.dumps({"done": True, "query_type": query_type})}

        except Exception as exc:
            logger.exception("Streaming analysis failed")
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}

    return EventSourceResponse(event_generator())
```

**Run tests:** `pytest code/tests/api/test_analyze.py -v`

**Commit:** `feat: add SSE streaming endpoint for agent analysis`

---

### Task 2: Add streaming tests

**Files:**
- Modify: `code/tests/api/test_analyze.py`

**Implementation:**

Add tests that mock the graph's `astream` method:

```python
import json

async def test_stream_returns_sse_events():
    """Streaming endpoint should return SSE events with tokens."""
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None):
        yield (
            AIMessageChunk(content="Your DPS is great."),
            {"langgraph_node": "analyze"},
        )

    mock_graph.astream = fake_astream

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze/stream",
                json={"question": "How is my DPS?"},
            )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    # Parse SSE events from body
    lines = [l for l in resp.text.strip().split("\n") if l.startswith("data:")]
    assert len(lines) >= 2  # at least one token + done
    token_event = json.loads(lines[0].removeprefix("data:").strip())
    assert "token" in token_event
    done_event = json.loads(lines[-1].removeprefix("data:").strip())
    assert done_event.get("done") is True


async def test_stream_strips_think_tags():
    """Streaming should buffer and strip think tags."""
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None):
        yield (
            AIMessageChunk(content="<think>reasoning"),
            {"langgraph_node": "analyze"},
        )
        yield (
            AIMessageChunk(content="</think>Clean answer."),
            {"langgraph_node": "analyze"},
        )

    mock_graph.astream = fake_astream

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze/stream",
                json={"question": "How is my DPS?"},
            )
    lines = [l for l in resp.text.strip().split("\n") if l.startswith("data:")]
    # Should not contain think tags in any token
    all_text = ""
    for line in lines:
        event = json.loads(line.removeprefix("data:").strip())
        if "token" in event:
            all_text += event["token"]
    assert "<think>" not in all_text
    assert "Clean answer" in all_text


async def test_stream_skips_non_analyze_nodes():
    """Only tokens from the analyze node should be streamed."""
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None):
        yield (
            AIMessageChunk(content="my_performance"),
            {"langgraph_node": "route"},
        )
        yield (
            AIMessageChunk(content="The answer."),
            {"langgraph_node": "analyze"},
        )

    mock_graph.astream = fake_astream

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze/stream",
                json={"question": "Show my DPS"},
            )
    lines = [l for l in resp.text.strip().split("\n") if l.startswith("data:")]
    all_tokens = ""
    for line in lines:
        event = json.loads(line.removeprefix("data:").strip())
        if "token" in event:
            all_tokens += event["token"]
    assert "my_performance" not in all_tokens
    assert "The answer" in all_tokens


async def test_stream_handles_error():
    """Errors during streaming should emit an error event."""
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None):
        raise Exception("Connection refused")
        yield  # make it a generator

    mock_graph.astream = fake_astream

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze/stream",
                json={"question": "How is my DPS?"},
            )
    assert resp.status_code == 200  # SSE always starts with 200
    assert "error" in resp.text.lower() or "Connection refused" in resp.text
```

**Run tests:** `pytest code/tests/api/test_analyze.py -v`

**Commit:** `test: add streaming endpoint tests`

---

### Task 3: Add streaming API client to frontend

**Files:**
- Modify: `code/frontend/src/lib/api.ts`

**Implementation:**

Add `postAnalyzeStream` function:

```typescript
export function postAnalyzeStream(
  question: string,
  onToken: (token: string) => void,
  onDone: (queryType: string | null) => void,
  onError: (message: string) => void,
): AbortController {
  const controller = new AbortController()

  ;(async () => {
    try {
      const res = await fetch('/api/analyze/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText)
        onError(`${res.status}: ${detail}`)
        return
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let partial = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        partial += decoder.decode(value, { stream: true })
        const lines = partial.split('\n')
        partial = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          const raw = line.slice(5).trim()
          if (!raw) continue

          try {
            const event = JSON.parse(raw)
            if (event.token) {
              onToken(event.token)
            } else if (event.done) {
              onDone(event.query_type ?? null)
            } else if (event.detail) {
              onError(event.detail)
            }
          } catch {
            // skip malformed SSE lines
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        onError(err instanceof Error ? err.message : 'Stream failed')
      }
    }
  })()

  return controller
}
```

**Commit:** `feat: add streaming API client for chat`

---

### Task 4: Update ChatPage to use streaming

**Files:**
- Modify: `code/frontend/src/pages/ChatPage.tsx`
- Modify: `code/frontend/src/components/chat/MessageList.tsx`

**Implementation:**

Update ChatPage to use `postAnalyzeStream` instead of `postAnalyze`:

```tsx
import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { postAnalyzeStream } from '../lib/api'
import type { ChatMessage } from '../lib/types'
import ChatInput from '../components/chat/ChatInput'
import MessageList from '../components/chat/MessageList'

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    (question: string) => {
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: question,
        timestamp: Date.now(),
      }
      const assistantId = crypto.randomUUID()
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, userMsg, assistantMsg])
      setStreaming(true)

      abortRef.current = postAnalyzeStream(
        question,
        (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token } : m,
            ),
          )
        },
        (queryType) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, queryType } : m,
            ),
          )
          setStreaming(false)
        },
        (error) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content || `Error: ${error}` }
                : m,
            ),
          )
          setStreaming(false)
        },
      )
    },
    [],
  )

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    const q = searchParams.get('q')
    if (q) {
      setSearchParams({}, { replace: true })
      sendMessage(q)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex h-full flex-col -m-6">
      <MessageList messages={messages} streaming={streaming} />
      <ChatInput onSend={sendMessage} disabled={streaming} />
    </div>
  )
}
```

Update MessageList — replace `loading` spinner with streaming cursor:

```tsx
import { useEffect, useRef } from 'react'
import type { ChatMessage } from '../../lib/types'
import MessageBubble from './MessageBubble'

interface Props {
  messages: ChatMessage[]
  streaming?: boolean
}

export default function MessageList({ messages, streaming }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming])

  if (messages.length === 0 && !streaming) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 text-zinc-500">
        <div className="text-6xl">&#9876;</div>
        <h2 className="text-lg font-semibold text-zinc-300">Shukketsu Raid Analyzer</h2>
        <p className="max-w-md text-center text-sm">
          Ask about your raid performance, compare kills to top guilds, track progression,
          or analyze any encounter.
        </p>
        <div className="mt-2 grid gap-2 text-xs">
          <span className="rounded bg-zinc-800 px-3 py-1.5">&quot;How did I do on Patchwerk?&quot;</span>
          <span className="rounded bg-zinc-800 px-3 py-1.5">&quot;Compare our Naxx run to top guilds&quot;</span>
          <span className="rounded bg-zinc-800 px-3 py-1.5">&quot;What spec tops DPS on Thaddius?&quot;</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
```

The empty assistant message with `content: ""` will render as an empty bubble with a blinking cursor effect. As tokens arrive, the markdown renders incrementally. No separate spinner needed — the growing text IS the progress indicator.

**Build frontend:** `cd code/frontend && npm run build`

**Commit:** `feat: stream agent responses token-by-token in chat UI`

---

### Task 5: Update CLAUDE.md

Add to resolved issues:
```markdown
- **No streaming:** `POST /api/analyze/stream` SSE endpoint streams analysis tokens. Think-tag buffering strips `<think>...</think>` before forwarding. Frontend uses fetch + ReadableStream for incremental message rendering.
```

**Commit:** `docs: add streaming endpoint to resolved issues`
