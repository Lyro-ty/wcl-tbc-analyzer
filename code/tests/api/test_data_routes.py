"""Tests for data API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_session_factory():
    """Factory that returns an AsyncMock session."""
    mock_session = AsyncMock()
    factory = MagicMock(return_value=mock_session)
    return factory, mock_session


@pytest.fixture
def app(mock_session_factory):
    factory, _ = mock_session_factory
    with patch("shukketsu.api.routes.data._session_factory", factory):
        from shukketsu.api.app import create_app
        return create_app()


def _mock_settings(has_creds=True):
    """Create a mock settings object for WCL endpoints."""
    settings = MagicMock()
    settings.wcl.client_id = "test_id" if has_creds else ""
    settings.wcl.client_secret.get_secret_value.return_value = "test_secret"
    settings.wcl.oauth_url = "https://www.warcraftlogs.com/oauth/token"
    return settings


class TestFightAbilities:
    async def test_returns_abilities(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(_mapping={
                "player_name": "TestWarr", "metric_type": "damage",
                "ability_name": "Mortal Strike", "spell_id": 12294,
                "total": 50000, "hit_count": 20, "crit_count": 10,
                "crit_pct": 50.0, "pct_of_total": 45.0,
            }),
        ]
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/abilities")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["ability_name"] == "Mortal Strike"

    async def test_404_when_no_data(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/abilities")

        assert resp.status_code == 404


class TestPlayerAbilities:
    async def test_returns_player_abilities(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(_mapping={
                "player_name": "TestWarr", "metric_type": "damage",
                "ability_name": "Whirlwind", "spell_id": 1680,
                "total": 30000, "hit_count": 40, "crit_count": 8,
                "crit_pct": 20.0, "pct_of_total": 30.0,
            }),
        ]
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/abilities/TestWarr")

        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["player_name"] == "TestWarr"


class TestFightBuffs:
    async def test_returns_buffs(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(_mapping={
                "player_name": "TestWarr", "metric_type": "buff",
                "ability_name": "Battle Shout", "spell_id": 2048,
                "uptime_pct": 95.0, "stack_count": 0.0,
            }),
        ]
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/buffs")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["ability_name"] == "Battle Shout"
        assert data[0]["uptime_pct"] == 95.0

    async def test_404_when_no_data(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/buffs")

        assert resp.status_code == 404


class TestAbilitiesAvailable:
    async def test_returns_true_when_data_exists(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(has_data=True)
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/abilities-available")

        assert resp.status_code == 200
        assert resp.json()["has_data"] is True

    async def test_returns_false_when_no_data(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(has_data=False)
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/abilities-available")

        assert resp.status_code == 200
        assert resp.json()["has_data"] is False


class TestFetchTableData:
    async def test_200_success(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_ingest = AsyncMock(return_value=42)

        with (
            patch("shukketsu.api.routes.data._session_factory", factory),
            patch("shukketsu.config.get_settings", return_value=_mock_settings()),
            patch(
                "shukketsu.pipeline.table_data.ingest_table_data_for_report",
                mock_ingest,
            ),
            patch("shukketsu.wcl.auth.WCLAuth"),
            patch("shukketsu.wcl.client.WCLClient") as mock_wcl_cls,
        ):
            mock_wcl_cls.return_value.__aenter__ = AsyncMock()
            mock_wcl_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/api/data/reports/abc123/table-data")

        assert resp.status_code == 200
        data = resp.json()
        assert data["report_code"] == "abc123"
        assert data["table_rows"] == 42

    async def test_503_no_creds(self, app, mock_session_factory):
        factory, _ = mock_session_factory
        with (
            patch("shukketsu.api.routes.data._session_factory", factory),
            patch(
                "shukketsu.config.get_settings",
                return_value=_mock_settings(has_creds=False),
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/api/data/reports/abc123/table-data")

        assert resp.status_code == 503


class TestRefreshRankings:
    async def test_503_no_creds(self, app, mock_session_factory):
        factory, _ = mock_session_factory
        with (
            patch("shukketsu.api.routes.data._session_factory", factory),
            patch(
                "shukketsu.config.get_settings",
                return_value=_mock_settings(has_creds=False),
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/api/data/rankings/refresh")

        assert resp.status_code == 503

    async def test_404_no_encounters(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        with (
            patch("shukketsu.api.routes.data._session_factory", factory),
            patch("shukketsu.config.get_settings", return_value=_mock_settings()),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/api/data/rankings/refresh")

        assert resp.status_code == 404


class TestRefreshSpeedRankings:
    async def test_503_no_creds(self, app, mock_session_factory):
        factory, _ = mock_session_factory
        with (
            patch("shukketsu.api.routes.data._session_factory", factory),
            patch(
                "shukketsu.config.get_settings",
                return_value=_mock_settings(has_creds=False),
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/api/data/speed-rankings/refresh")

        assert resp.status_code == 503

    async def test_404_no_encounters(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        with (
            patch("shukketsu.api.routes.data._session_factory", factory),
            patch("shukketsu.config.get_settings", return_value=_mock_settings()),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/api/data/speed-rankings/refresh")

        assert resp.status_code == 404


class TestCharacterProfile:
    async def test_200_success(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(_mapping={
            "id": 1, "name": "Lyro", "server_slug": "whitemane",
            "server_region": "US", "character_class": "Warrior",
            "spec": "Arms", "total_fights": 50, "total_kills": 40,
            "total_deaths": 5, "avg_dps": 1200.5, "best_dps": 1800.3,
            "avg_parse": 75.2, "best_parse": 98.0, "avg_ilvl": 100.5,
        })
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get("/api/data/characters/Lyro/profile")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Lyro"
        assert data["total_fights"] == 50

    async def test_404_not_found(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get("/api/data/characters/Nobody/profile")

        assert resp.status_code == 404


class TestCharacterRecentParses:
    async def test_200_success(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(_mapping={
                "encounter_name": "Patchwerk", "dps": 1500.0, "hps": 0.0,
                "parse_percentile": 85.0, "deaths": 0, "item_level": 100.0,
                "player_class": "Warrior", "player_spec": "Arms",
                "kill": True, "duration_ms": 120000,
                "report_code": "abc123", "fight_id": 1,
                "report_date": 1700000000000,
            }),
        ]
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/data/characters/Lyro/recent-parses"
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["encounter_name"] == "Patchwerk"


class TestDashboardStats:
    async def test_200_success(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(_mapping={
            "total_reports": 10, "total_kills": 80,
            "total_wipes": 20, "total_characters": 3,
            "total_encounters": 15,
        })
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get("/api/data/dashboard/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reports"] == 10
        assert data["total_kills"] == 80


class TestFightDeaths:
    async def test_returns_deaths(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(_mapping={
                "player_name": "TestWarr", "death_index": 1,
                "timestamp_ms": 45000, "killing_blow_ability": "Hateful Strike",
                "killing_blow_source": "Patchwerk",
                "damage_taken_total": 28000, "events_json": "[]",
            }),
        ]
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/deaths")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["killing_blow_ability"] == "Hateful Strike"

    async def test_empty_when_no_deaths(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/fights/1/deaths")

        assert resp.status_code == 200
        assert resp.json() == []


class TestFightCastMetrics:
    async def test_returns_metrics(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(_mapping={
            "player_name": "TestWarr", "total_casts": 150,
            "casts_per_minute": 32.5, "gcd_uptime_pct": 88.3,
            "active_time_ms": 240000, "downtime_ms": 32000,
            "longest_gap_ms": 5000, "longest_gap_at_ms": 120000,
            "avg_gap_ms": 3200.0, "gap_count": 4,
        })
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/data/reports/abc123/fights/1/cast-metrics/TestWarr"
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["gcd_uptime_pct"] == 88.3
        assert data["total_casts"] == 150

    async def test_null_when_no_data(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/data/reports/abc123/fights/1/cast-metrics/TestWarr"
                )

        assert resp.status_code == 200
        assert resp.json() is None


class TestFightCooldowns:
    async def test_returns_cooldowns(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(_mapping={
                "player_name": "TestWarr", "ability_name": "Death Wish",
                "spell_id": 12292, "cooldown_sec": 180,
                "times_used": 2, "max_possible_uses": 3,
                "first_use_ms": 5000, "last_use_ms": 190000,
                "efficiency_pct": 66.7,
            }),
        ]
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/data/reports/abc123/fights/1/cooldowns/TestWarr"
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["ability_name"] == "Death Wish"
        assert data[0]["efficiency_pct"] == 66.7


class TestEventsAvailable:
    async def test_returns_true_when_data_exists(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(has_data=True)
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/events-available")

        assert resp.status_code == 200
        assert resp.json()["has_data"] is True

    async def test_returns_false_when_no_data(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(has_data=False)
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/data/reports/abc123/events-available")

        assert resp.status_code == 200
        assert resp.json()["has_data"] is False


class TestFetchEventData:
    async def test_200_success(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_ingest = AsyncMock(return_value=25)

        with (
            patch("shukketsu.api.routes.data._session_factory", factory),
            patch("shukketsu.config.get_settings", return_value=_mock_settings()),
            patch(
                "shukketsu.pipeline.event_data.ingest_event_data_for_report",
                mock_ingest,
            ),
            patch("shukketsu.wcl.auth.WCLAuth"),
            patch("shukketsu.wcl.client.WCLClient") as mock_wcl_cls,
        ):
            mock_wcl_cls.return_value.__aenter__ = AsyncMock()
            mock_wcl_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/api/data/reports/abc123/event-data")

        assert resp.status_code == 200
        data = resp.json()
        assert data["report_code"] == "abc123"
        assert data["event_rows"] == 25

    async def test_503_no_creds(self, app, mock_session_factory):
        factory, _ = mock_session_factory
        with (
            patch("shukketsu.api.routes.data._session_factory", factory),
            patch(
                "shukketsu.config.get_settings",
                return_value=_mock_settings(has_creds=False),
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post("/api/data/reports/abc123/event-data")

        assert resp.status_code == 503


class TestDashboardRecent:
    async def test_200_success(self, app, mock_session_factory):
        factory, mock_session = mock_session_factory
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(_mapping={
                "code": "abc123", "title": "Naxx Clear",
                "guild_name": "Shukketsu", "start_time": 1700000000000,
                "fight_count": 15, "kill_count": 13,
                "wipe_count": 2, "avg_kill_dps": 1200.5,
            }),
        ]
        mock_session.execute.return_value = mock_result

        with patch("shukketsu.api.routes.data._session_factory", factory):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get("/api/data/dashboard/recent")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "abc123"
