import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, AIMessageChunk

from shukketsu.api.routes.analyze import _strip_think_tags


@pytest.fixture
def mock_graph():
    graph = AsyncMock()
    graph.ainvoke.return_value = {
        "messages": [
            AIMessage(content="Your DPS on Gruul is 1500, a 95th percentile parse."),
        ],
    }
    return graph


@pytest.fixture
def app(mock_graph):
    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        from shukketsu.api.app import create_app
        return create_app()


async def test_analyze_returns_200(app, mock_graph):
    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze",
                json={"question": "How is my DPS on Gruul?"},
            )
    assert resp.status_code == 200


async def test_analyze_validates_input(app, mock_graph):
    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/analyze", json={})
    assert resp.status_code == 422


async def test_analyze_returns_analysis(app, mock_graph):
    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze",
                json={"question": "How is my DPS on Gruul?"},
            )
    body = resp.json()
    assert "answer" in body
    assert "1500" in body["answer"]


async def test_analyze_handles_llm_unavailable():
    error_graph = AsyncMock()
    error_graph.ainvoke.side_effect = Exception("Connection refused")

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=error_graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze",
                json={"question": "How is my DPS?"},
            )
    assert resp.status_code == 503


class TestStripThinkTags:
    def test_no_tags_passthrough(self):
        assert _strip_think_tags("Normal response") == "Normal response"

    def test_strips_closing_think_prefix(self):
        assert _strip_think_tags("</think>The answer") == "The answer"

    def test_strips_full_think_block(self):
        text = "<think>Some reasoning here</think>The answer"
        assert _strip_think_tags(text) == "The answer"

    def test_strips_multiline_think_block(self):
        text = "<think>\nstep 1\nstep 2\n</think>\nThe answer"
        assert _strip_think_tags(text) == "The answer"

    def test_preserves_think_in_middle_of_text(self):
        # Only strips prefix think tags (up to first </think>)
        text = "Start </think> middle"
        assert _strip_think_tags(text) == "middle"

    def test_empty_string(self):
        assert _strip_think_tags("") == ""

    def test_strips_with_whitespace_after_tag(self):
        assert _strip_think_tags("</think>   Clean output") == "Clean output"


async def test_analyze_strips_think_tags():
    graph = AsyncMock()
    graph.ainvoke.return_value = {
        "messages": [
            AIMessage(content="<think>reasoning</think>Your DPS is 1500."),
        ],
    }

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze",
                json={"question": "How is my DPS?"},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert "<think>" not in body["answer"]
    assert "Your DPS is 1500." in body["answer"]


async def test_analyze_handles_no_data():
    empty_graph = AsyncMock()
    empty_graph.ainvoke.return_value = {
        "messages": [AIMessage(content="No performance data found for your character.")],
    }

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=empty_graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze",
                json={"question": "Show me my latest parses"},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert "No performance data" in body["answer"]


# --- Streaming endpoint tests ---


async def test_stream_returns_sse_events():
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None, config=None):
        yield (
            AIMessageChunk(content="Your DPS is 1500."),
            {"langgraph_node": "agent"},
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
    assert "text/event-stream" in resp.headers["content-type"]

    body = resp.text
    # Parse data lines from SSE body
    data_lines = [
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data:")
    ]

    token_events = [json.loads(d) for d in data_lines if "token" in d]
    done_events = [json.loads(d) for d in data_lines if "done" in d]

    assert len(token_events) >= 1
    assert any("1500" in evt["token"] for evt in token_events)
    assert len(done_events) == 1
    assert done_events[0]["done"] is True


async def test_stream_strips_think_tags():
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None, config=None):
        yield (
            AIMessageChunk(content="<think>reasoning"),
            {"langgraph_node": "agent"},
        )
        yield (
            AIMessageChunk(content="</think>Clean answer."),
            {"langgraph_node": "agent"},
        )

    mock_graph.astream = fake_astream

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze/stream",
                json={"question": "Analyze my performance"},
            )

    body = resp.text
    data_lines = [
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data:")
    ]

    token_events = [json.loads(d) for d in data_lines if "token" in d]
    all_tokens = "".join(evt["token"] for evt in token_events)

    assert "<think>" not in all_tokens
    assert "Clean answer." in all_tokens


async def test_stream_skips_non_agent_nodes():
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None, config=None):
        yield (
            AIMessageChunk(content="Tool result data"),
            {"langgraph_node": "tools"},
        )
        yield (
            AIMessageChunk(content="Your parse is 95th percentile."),
            {"langgraph_node": "agent"},
        )

    mock_graph.astream = fake_astream

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze/stream",
                json={"question": "How are my parses?"},
            )

    body = resp.text
    data_lines = [
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data:")
    ]

    token_events = [json.loads(d) for d in data_lines if "token" in d]
    all_tokens = "".join(evt["token"] for evt in token_events)

    assert "95th percentile" in all_tokens
    assert "Tool result" not in all_tokens


async def test_stream_handles_error():
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None, config=None):
        raise Exception("LLM connection refused")
        # Make this an async generator that raises
        yield  # pragma: no cover

    mock_graph.astream = fake_astream

    with patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/analyze/stream",
                json={"question": "What is my DPS?"},
            )

    assert resp.status_code == 200
    body = resp.text
    assert "Analysis failed" in body


# --- Langfuse callback wiring tests ---


async def test_analyze_passes_langfuse_callbacks():
    """When a langfuse handler is set, it's passed as callbacks config."""
    mock_handler = object()  # Dummy handler
    graph = AsyncMock()
    graph.ainvoke.return_value = {
        "messages": [AIMessage(content="Analysis result.")],
    }

    with (
        patch("shukketsu.api.routes.analyze._get_graph", return_value=graph),
        patch(
            "shukketsu.api.routes.analyze._get_langfuse_handler",
            return_value=mock_handler,
        ),
    ):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/analyze",
                json={"question": "Test question"},
            )

    # Verify callbacks were passed in the config dict
    call_kwargs = graph.ainvoke.call_args
    config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config", {})
    assert mock_handler in config.get("callbacks", [])


async def test_analyze_no_callbacks_without_handler():
    """When no langfuse handler is set, no callbacks config is passed."""
    graph = AsyncMock()
    graph.ainvoke.return_value = {
        "messages": [AIMessage(content="Analysis result.")],
    }

    with (
        patch("shukketsu.api.routes.analyze._get_graph", return_value=graph),
        patch(
            "shukketsu.api.routes.analyze._get_langfuse_handler",
            return_value=None,
        ),
    ):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/analyze",
                json={"question": "Test question"},
            )

    call_kwargs = graph.ainvoke.call_args
    # Either no config, or config without callbacks
    config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config", {})
    assert "callbacks" not in config or config["callbacks"] == []


async def test_stream_passes_langfuse_callbacks():
    """When a langfuse handler is set, streaming also gets callbacks."""
    mock_handler = object()
    mock_graph = AsyncMock()
    astream_config_capture = {}

    async def fake_astream(input, stream_mode=None, config=None):
        astream_config_capture["config"] = config or {}
        yield (
            AIMessageChunk(content="Streamed result."),
            {"langgraph_node": "agent"},
        )

    mock_graph.astream = fake_astream

    with (
        patch("shukketsu.api.routes.analyze._get_graph", return_value=mock_graph),
        patch(
            "shukketsu.api.routes.analyze._get_langfuse_handler",
            return_value=mock_handler,
        ),
    ):
        from shukketsu.api.app import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/analyze/stream",
                json={"question": "Test question"},
            )

    assert mock_handler in astream_config_capture["config"].get("callbacks", [])


# --- Lifespan Langfuse wiring tests ---


async def test_lifespan_creates_langfuse_handler_when_enabled(monkeypatch):
    """When LANGFUSE__ENABLED=true, lifespan sets up the handler."""
    monkeypatch.setenv("LANGFUSE__ENABLED", "true")
    monkeypatch.setenv("LANGFUSE__PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE__SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE__HOST", "http://localhost:3000")

    from shukketsu.config import get_settings
    get_settings.cache_clear()

    mock_langfuse_cls = MagicMock()
    mock_cb_handler = MagicMock()

    with (
        patch("shukketsu.api.app.create_db_engine") as mock_engine,
        patch("shukketsu.api.app.create_session_factory") as mock_sf,
        patch("shukketsu.api.app.create_llm"),
        patch("shukketsu.api.app.create_graph"),
        patch("shukketsu.api.app.set_session_factory"),
        patch("shukketsu.api.app.set_dependencies"),
        patch("shukketsu.api.app.set_graph"),
        patch("shukketsu.api.app.set_health_deps"),
        patch("shukketsu.api.app.set_langfuse_handler") as mock_set_handler,
        patch.dict("sys.modules", {
            "langfuse": MagicMock(Langfuse=mock_langfuse_cls),
            "langfuse.langchain": MagicMock(CallbackHandler=mock_cb_handler),
        }),
    ):
        mock_engine.return_value = AsyncMock()
        mock_sf.return_value = AsyncMock()

        from shukketsu.api.app import create_app
        app = create_app()

        async with app.router.lifespan_context(app):
            pass

    mock_langfuse_cls.assert_called_once_with(
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        host="http://localhost:3000",
    )
    mock_set_handler.assert_called_once_with(mock_cb_handler)
    get_settings.cache_clear()


async def test_lifespan_skips_langfuse_when_disabled(monkeypatch):
    """When LANGFUSE__ENABLED=false (default), no handler is created."""
    monkeypatch.setenv("LANGFUSE__ENABLED", "false")

    from shukketsu.config import get_settings
    get_settings.cache_clear()

    with (
        patch("shukketsu.api.app.create_db_engine") as mock_engine,
        patch("shukketsu.api.app.create_session_factory") as mock_sf,
        patch("shukketsu.api.app.create_llm"),
        patch("shukketsu.api.app.create_graph"),
        patch("shukketsu.api.app.set_session_factory"),
        patch("shukketsu.api.app.set_dependencies"),
        patch("shukketsu.api.app.set_graph"),
        patch("shukketsu.api.app.set_health_deps"),
        patch("shukketsu.api.app.set_langfuse_handler") as mock_set_handler,
    ):
        mock_engine.return_value = AsyncMock()
        mock_sf.return_value = AsyncMock()

        from shukketsu.api.app import create_app
        app = create_app()

        async with app.router.lifespan_context(app):
            pass

    mock_set_handler.assert_not_called()
    get_settings.cache_clear()


# --- Streaming semaphore tests ---


class TestAnalyzeStreamSemaphore:
    def test_stream_uses_semaphore(self):
        """Streaming endpoint must use the same LLM semaphore as /analyze."""
        import inspect

        from shukketsu.api.routes import analyze as mod

        source = inspect.getsource(mod.analyze_stream)
        assert "_llm_semaphore" in source


class TestStreamingBufferLimit:
    def test_think_buffer_has_max_size(self):
        """Streaming think-tag buffer must have a maximum size."""
        from shukketsu.api.routes import analyze as mod
        assert hasattr(mod, '_MAX_THINK_BUFFER')
        assert mod._MAX_THINK_BUFFER > 0


async def test_stream_resets_buffer_between_agent_turns():
    """Think-tag buffer must reset when tools node fires between agent calls."""
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None, config=None):
        # First agent turn: think tags (intermediate)
        yield (
            AIMessageChunk(content="<think>Let me look that up</think>"),
            {"langgraph_node": "agent"},
        )
        # Tools node fires (resets buffer)
        yield (
            AIMessageChunk(content="DPS: 1500"),
            {"langgraph_node": "tools"},
        )
        # Second agent turn: think tags + final response
        yield (
            AIMessageChunk(content="<think>Now I can analyze</think>"),
            {"langgraph_node": "agent"},
        )
        yield (
            AIMessageChunk(content="Your DPS of 1500 is excellent."),
            {"langgraph_node": "agent"},
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

    body = resp.text
    data_lines = [
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data:")
    ]

    token_events = [json.loads(d) for d in data_lines if "token" in d]
    all_tokens = "".join(evt["token"] for evt in token_events)

    assert "<think>" not in all_tokens
    assert "Let me look that up" not in all_tokens
    assert "1500 is excellent" in all_tokens


async def test_stream_skips_tool_call_chunks():
    """Chunks with tool_call_chunks should not be streamed."""
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None, config=None):
        # Agent produces a tool call chunk (intermediate)
        chunk = AIMessageChunk(content="")
        chunk.tool_call_chunks = [
            {"name": "get_my_performance", "args": '{"encounter_name": "Gruul"}',
             "id": "1", "index": 0}
        ]
        yield (chunk, {"langgraph_node": "agent"})
        # Tools node
        yield (AIMessageChunk(content="DPS: 1500"), {"langgraph_node": "tools"})
        # Final agent response
        yield (
            AIMessageChunk(content="Your DPS is great."),
            {"langgraph_node": "agent"},
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

    body = resp.text
    data_lines = [
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data:")
    ]

    token_events = [json.loads(d) for d in data_lines if "token" in d]
    all_tokens = "".join(evt["token"] for evt in token_events)

    assert "DPS is great" in all_tokens
    assert "get_my_performance" not in all_tokens
