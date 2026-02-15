from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage


@pytest.fixture
def mock_graph():
    graph = AsyncMock()
    graph.ainvoke.return_value = {
        "messages": [AIMessage(content="Your DPS on Gruul is 1500, which is a 95th percentile parse.")],
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
