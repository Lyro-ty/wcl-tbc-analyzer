import json
from unittest.mock import AsyncMock, patch

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
        "query_type": "my_performance",
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
    assert body["query_type"] == "my_performance"


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
        "query_type": "my_performance",
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
        "query_type": "my_performance",
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


async def test_stream_skips_non_analyze_nodes():
    mock_graph = AsyncMock()

    async def fake_astream(input, stream_mode=None, config=None):
        yield (
            AIMessageChunk(content="Routing to performance query"),
            {"langgraph_node": "route"},
        )
        yield (
            AIMessageChunk(content="Your parse is 95th percentile."),
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
    assert "Routing" not in all_tokens


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
    assert "LLM connection refused" in body


# --- Langfuse callback wiring tests ---


async def test_analyze_passes_langfuse_callbacks():
    """When a langfuse handler is set, it's passed as callbacks config."""
    mock_handler = object()  # Dummy handler
    graph = AsyncMock()
    graph.ainvoke.return_value = {
        "messages": [AIMessage(content="Analysis result.")],
        "query_type": "general",
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
        "query_type": "general",
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
            {"langgraph_node": "analyze"},
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
