"""Tests for event-data endpoints: cast metrics, cooldowns, resources, etc."""

from unittest.mock import AsyncMock, MagicMock

from tests.api.conftest import make_row

# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/cast-metrics/{player}
# ---------------------------------------------------------------------------

async def test_cast_metrics_ok(client, mock_session):
    """Returns cast metrics for a player in a fight."""
    mock_row = make_row(
        player_name="Lyro", total_casts=150, casts_per_minute=25.0,
        gcd_uptime_pct=92.5, active_time_ms=108000, downtime_ms=12000,
        longest_gap_ms=5000, longest_gap_at_ms=45000,
        avg_gap_ms=800.0, gap_count=15,
    )
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/cast-metrics/Lyro"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["player_name"] == "Lyro"
    assert data["gcd_uptime_pct"] == 92.5
    assert data["total_casts"] == 150


async def test_cast_metrics_null(client, mock_session):
    """Returns null when no cast metrics available."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/cast-metrics/NoSuch"
    )
    assert resp.status_code == 200
    assert resp.json() is None


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/cooldowns/{player}
# ---------------------------------------------------------------------------

async def test_cooldowns_ok(client, mock_session):
    """Returns cooldown usage for a player."""
    mock_row = make_row(
        player_name="Lyro", ability_name="Recklessness", spell_id=1719,
        cooldown_sec=300, times_used=2, max_possible_uses=3,
        first_use_ms=5000, last_use_ms=305000, efficiency_pct=66.7,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/cooldowns/Lyro"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ability_name"] == "Recklessness"
    assert data[0]["efficiency_pct"] == 66.7


async def test_cooldowns_empty(client, mock_session):
    """Returns empty list when no cooldown data (not 404)."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/cooldowns/Lyro"
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/cancelled-casts/{player}
# ---------------------------------------------------------------------------

async def test_cancelled_casts_ok(client, mock_session):
    """Returns cancelled cast metrics for a player."""
    mock_row = make_row(
        player_name="Lyro", total_begins=100, total_completions=85,
        cancel_count=15, cancel_pct=15.0,
        top_cancelled_json='[{"spell": "Slam", "count": 10}]',
    )
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/cancelled-casts/Lyro"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cancel_pct"] == 15.0
    assert data["cancel_count"] == 15


async def test_cancelled_casts_null(client, mock_session):
    """Returns null when no cancelled cast data."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/cancelled-casts/NoSuch"
    )
    assert resp.status_code == 200
    assert resp.json() is None


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/cast-timeline/{player}
# ---------------------------------------------------------------------------

async def test_cast_timeline_ok(client, mock_session):
    """Returns cast event timeline for a player."""
    rows = [
        make_row(
            player_name="Lyro", timestamp_ms=1000 * i,
            spell_id=12294, ability_name="Mortal Strike",
            event_type="cast", target_name="Patchwerk",
        )
        for i in range(1, 4)
    ]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/cast-timeline/Lyro"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert data[0]["ability_name"] == "Mortal Strike"


async def test_cast_timeline_empty(client, mock_session):
    """Returns empty list when no cast events."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/cast-timeline/Lyro"
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/resources/{player}
# ---------------------------------------------------------------------------

async def test_resources_ok(client, mock_session):
    """Returns resource snapshots for a player."""
    mock_row = make_row(
        player_name="Lyro", resource_type="rage",
        min_value=0, max_value=100, avg_value=45.5,
        time_at_zero_ms=5000, time_at_zero_pct=4.2,
        samples_json=None,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/resources/Lyro"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["resource_type"] == "rage"
    assert data[0]["avg_value"] == 45.5


async def test_resources_empty(client, mock_session):
    """Returns empty list when no resource data."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/resources/Lyro"
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/cooldown-windows/{player}
# ---------------------------------------------------------------------------

async def test_cooldown_windows_ok(client, mock_session):
    """Returns cooldown window DPS estimates."""
    mock_row = make_row(
        player_name="Lyro", ability_name="Recklessness", spell_id=1719,
        cooldown_sec=10, first_use_ms=5000, baseline_dps=2000.0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/cooldown-windows/Lyro"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ability_name"] == "Recklessness"
    assert data[0]["dps_gain_pct"] == 20.0
    # window_dps should be baseline * 1.2
    assert data[0]["window_dps"] == 2400.0
    assert data[0]["baseline_dps"] == 2000.0


async def test_cooldown_windows_empty(client, mock_session):
    """Returns empty list when no cooldown windows."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/cooldown-windows/Lyro"
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/rotation/{player}
# ---------------------------------------------------------------------------

async def test_rotation_score_ok(client, mock_session):
    """Returns rotation score for a player."""
    # The endpoint makes 3 queries:
    # 1. PLAYER_FIGHT_INFO
    # 2. FIGHT_CAST_METRICS
    # 3. FIGHT_COOLDOWNS
    info_row = make_row(
        player_name="Lyro", player_class="Warrior", player_spec="Arms",
        dps=2500.0, encounter_id=201101, fight_duration_ms=120000,
    )
    cm_row = make_row(
        player_name="Lyro", total_casts=150, casts_per_minute=25.0,
        gcd_uptime_pct=92.5, active_time_ms=108000, downtime_ms=12000,
        longest_gap_ms=5000, longest_gap_at_ms=45000,
        avg_gap_ms=800.0, gap_count=15,
    )
    cd_row = make_row(
        player_name="Lyro", ability_name="Recklessness", spell_id=1719,
        cooldown_sec=300, times_used=2, max_possible_uses=3,
        first_use_ms=5000, last_use_ms=305000, efficiency_pct=80.0,
    )

    info_result = MagicMock()
    info_result.fetchone.return_value = info_row
    cm_result = MagicMock()
    cm_result.fetchone.return_value = cm_row
    cd_result = MagicMock()
    cd_result.fetchall.return_value = [cd_row]

    mock_session.execute = AsyncMock(
        side_effect=[info_result, cm_result, cd_result]
    )

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/rotation/Lyro"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["player_name"] == "Lyro"
    assert data["spec"] == "Arms"
    # 3 rules: GCD > 85% (pass), CPM > 20 (pass), CD >= 60% (pass)
    assert data["rules_checked"] == 3
    assert data["rules_passed"] == 3
    assert data["score_pct"] == 100.0


async def test_rotation_score_404(client, mock_session):
    """Returns 404 when player not found in fight."""
    info_result = MagicMock()
    info_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=info_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/rotation/NoSuch"
    )
    assert resp.status_code == 404


async def test_rotation_score_violations(client, mock_session):
    """Reports violations when rules fail."""
    info_row = make_row(
        player_name="Lyro", player_class="Warrior", player_spec="Arms",
        dps=1500.0, encounter_id=201101, fight_duration_ms=120000,
    )
    cm_row = make_row(
        player_name="Lyro", total_casts=60, casts_per_minute=10.0,
        gcd_uptime_pct=50.0, active_time_ms=60000, downtime_ms=60000,
        longest_gap_ms=15000, longest_gap_at_ms=30000,
        avg_gap_ms=2000.0, gap_count=30,
    )

    info_result = MagicMock()
    info_result.fetchone.return_value = info_row
    cm_result = MagicMock()
    cm_result.fetchone.return_value = cm_row
    cd_result = MagicMock()
    cd_result.fetchall.return_value = []

    mock_session.execute = AsyncMock(
        side_effect=[info_result, cm_result, cd_result]
    )

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/rotation/Lyro"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rules_checked"] == 2
    assert data["rules_passed"] == 0
    assert data["score_pct"] == 0.0
    assert data["violations_json"] is not None
    assert "GCD uptime" in data["violations_json"]
    assert "CPM" in data["violations_json"]


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/trinkets/{player}
# ---------------------------------------------------------------------------

async def test_trinket_procs_empty(client, mock_session):
    """Returns empty list when no trinket buffs found."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/trinkets/Lyro"
    )
    assert resp.status_code == 200
    assert resp.json() == []
