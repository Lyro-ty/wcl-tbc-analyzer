# Streaming Endpoint Design

## Goal

Add SSE (Server-Sent Events) streaming to the agent chat so users see the analysis response token-by-token instead of waiting 30-120 seconds with a spinner.

## Architecture

**Backend:** New `POST /api/analyze/stream` endpoint using LangGraph's `astream(stream_mode="messages")` filtered to the `analyze` node. Think-tag buffering strips Nemotron's `<think>...</think>` reasoning before forwarding tokens. Uses `sse_starlette.EventSourceResponse` (already installed).

**Frontend:** New `postAnalyzeStream()` in `lib/api.ts` using `fetch()` + `ReadableStream` reader to parse SSE lines. `ChatPage.tsx` creates an empty assistant message and incrementally appends tokens to it. No new dependencies.

**Backward compatibility:** The existing `POST /api/analyze` endpoint is unchanged.

## SSE Protocol

```
# Each token chunk:
data: {"token": "Here is"}

data: {"token": " your analysis"}

# Completion:
data: {"done": true, "query_type": "my_performance"}

# Error mid-stream:
event: error
data: {"detail": "Analysis service unavailable"}
```

## Think-Tag Buffering

Nemotron prepends `<think>...</think>` reasoning to responses. During streaming:

1. Accumulate tokens from the `analyze` node into a buffer
2. Scan buffer for `</think>` on each token
3. Once found, discard everything up to and including `</think>` + trailing whitespace
4. Forward all subsequent tokens immediately as SSE events
5. If no `</think>` appears (model didn't think), forward tokens directly after a small initial buffer check

## Backend Flow

```
POST /api/analyze/stream {question: "..."}
  → graph.astream(input, stream_mode="messages")
  → filter: only chunks where metadata.langgraph_node == "analyze"
  → buffer tokens until </think> detected (or not present)
  → yield SSE data events for each token
  → yield done event with query_type
  → on error: yield error event
```

## Frontend Flow

```
User submits question
  → append user ChatMessage to state
  → append empty assistant ChatMessage (content: "")
  → call postAnalyzeStream(question, onToken, onDone, onError)
  → onToken: update assistant message content += token
  → onDone: mark complete, store query_type
  → onError: show error in assistant message
```

## Files Changed

### Backend
- `code/shukketsu/api/routes/analyze.py` — add streaming endpoint + think-tag buffer logic
- `code/tests/api/test_analyze.py` — add streaming tests

### Frontend
- `code/frontend/src/lib/api.ts` — add `postAnalyzeStream()`
- `code/frontend/src/pages/ChatPage.tsx` — use streaming, update message incrementally
- `code/frontend/src/components/chat/MessageList.tsx` — replace spinner with cursor during streaming
