"""Tests for fight details, deaths, abilities, buffs, consumables, overheal, gear."""

from unittest.mock import AsyncMock, MagicMock

from tests.api.conftest import make_row

# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{fight_id}
# ---------------------------------------------------------------------------

async def test_fight_details_ok(client, mock_session):
    """Returns player performance rows for a specific fight."""
    mock_row = make_row(
        player_name="Lyro", player_class="Warrior", player_spec="Arms",
        dps=2500.0, hps=0.0, parse_percentile=92.0, deaths=0,
        interrupts=3, dispels=0, item_level=130.0, kill=True,
        duration_ms=120000, encounter_name="Patchwerk",
        report_title="Raid Night",
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["player_name"] == "Lyro"
    assert data[0]["dps"] == 2500.0
    assert data[0]["kill"] is True


async def test_fight_details_404(client, mock_session):
    """Returns 404 when fight not found."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/999")
    assert resp.status_code == 404


async def test_fight_details_multiple_players(client, mock_session):
    """Returns all players in the fight."""
    rows = [
        make_row(
            player_name=name, player_class=cls, player_spec=spec,
            dps=dps, hps=0.0, parse_percentile=80.0, deaths=0,
            interrupts=0, dispels=0, item_level=130.0, kill=True,
            duration_ms=120000, encounter_name="Patchwerk",
            report_title="Raid Night",
        )
        for name, cls, spec, dps in [
            ("Lyro", "Warrior", "Arms", 2500.0),
            ("Healer", "Priest", "Holy", 100.0),
        ]
    ]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/deaths
# ---------------------------------------------------------------------------

async def test_report_deaths_ok(client, mock_session):
    """Returns death entries for all fights in a report."""
    mock_row = make_row(
        fight_id=1, encounter_name="Patchwerk", player_name="Lyro",
        player_class="Warrior", player_spec="Arms",
        deaths=1, interrupts=3, dispels=0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/deaths")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["deaths"] == 1
    assert data[0]["encounter_name"] == "Patchwerk"


async def test_report_deaths_empty(client, mock_session):
    """Returns empty list when no death data (not 404)."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/deaths")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/deaths
# ---------------------------------------------------------------------------

async def test_fight_deaths_ok(client, mock_session):
    """Returns detailed death recaps for a fight."""
    mock_row = make_row(
        player_name="Lyro", death_index=0, timestamp_ms=45000,
        killing_blow_ability="Hateful Strike",
        killing_blow_source="Patchwerk",
        damage_taken_total=15000,
        events_json='[{"type": "damage", "amount": 15000}]',
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/deaths")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["killing_blow_ability"] == "Hateful Strike"


async def test_fight_deaths_empty(client, mock_session):
    """Returns empty list when no deaths in fight (not 404)."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/deaths")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/abilities
# ---------------------------------------------------------------------------

async def test_fight_abilities_ok(client, mock_session):
    """Returns ability metrics for all players in a fight."""
    mock_row = make_row(
        player_name="Lyro", metric_type="damage", ability_name="Mortal Strike",
        spell_id=12294, total=500000, hit_count=40, crit_count=15,
        crit_pct=37.5, pct_of_total=45.0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/abilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["ability_name"] == "Mortal Strike"
    assert data[0]["crit_pct"] == 37.5


async def test_fight_abilities_404(client, mock_session):
    """Returns 404 when no ability data (needs --with-tables)."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/abilities")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/abilities/{player}
# ---------------------------------------------------------------------------

async def test_player_abilities_ok(client, mock_session):
    """Returns ability metrics for a specific player."""
    mock_row = make_row(
        player_name="Lyro", metric_type="damage", ability_name="Slam",
        spell_id=1464, total=300000, hit_count=50, crit_count=10,
        crit_pct=20.0, pct_of_total=30.0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/abilities/Lyro")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["player_name"] == "Lyro"


async def test_player_abilities_404(client, mock_session):
    """Returns 404 when no ability data for player."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/abilities/NoSuch")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/buffs
# ---------------------------------------------------------------------------

async def test_fight_buffs_ok(client, mock_session):
    """Returns buff uptime data for a fight."""
    mock_row = make_row(
        player_name="Lyro", metric_type="buff", ability_name="Battle Shout",
        spell_id=2048, uptime_pct=95.0, stack_count=1.0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/buffs")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["ability_name"] == "Battle Shout"
    assert data[0]["uptime_pct"] == 95.0


async def test_fight_buffs_404(client, mock_session):
    """Returns 404 when no buff data for fight."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/buffs")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/buffs/{player}
# ---------------------------------------------------------------------------

async def test_player_buffs_ok(client, mock_session):
    """Returns buff data for a specific player."""
    mock_row = make_row(
        player_name="Lyro", metric_type="debuff", ability_name="Sunder Armor",
        spell_id=7386, uptime_pct=80.0, stack_count=5.0,
    )
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/buffs/Lyro")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["ability_name"] == "Sunder Armor"


async def test_player_buffs_404(client, mock_session):
    """Returns 404 when no buff data for player."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/buffs/NoSuch")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/consumables
# ---------------------------------------------------------------------------

async def test_fight_consumables_ok(client, mock_session):
    """Returns consumable audit with missing categories."""
    rows = [
        make_row(
            player_name="Lyro", category="flask",
            ability_name="Flask of Endless Rage", spell_id=53755,
        ),
        make_row(
            player_name="Lyro", category="food",
            ability_name="Fish Feast", spell_id=57399,
        ),
    ]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/consumables")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["player_name"] == "Lyro"
    assert len(data[0]["consumables"]) == 2
    # weapon_oil is nice-to-have and missing
    assert "weapon_oil" in data[0]["missing"]


async def test_fight_consumables_empty(client, mock_session):
    """Returns empty list when no consumable data."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/consumables")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_fight_consumables_missing_flask(client, mock_session):
    """Player without flask/elixir gets flask/elixir flagged as missing."""
    rows = [
        make_row(
            player_name="Lyro", category="food",
            ability_name="Fish Feast", spell_id=57399,
        ),
    ]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/reports/abc123/fights/1/consumables")
    data = resp.json()
    assert "flask/elixir" in data[0]["missing"]


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/overheal/{player}
# ---------------------------------------------------------------------------

async def test_fight_overheal_ok(client, mock_session):
    """Returns overheal breakdown for a healer."""
    rows = [
        make_row(
            ability_name="Greater Heal", spell_id=2060,
            total=500000, overheal_total=100000, overheal_pct=16.7,
        ),
        make_row(
            ability_name="Prayer of Mending", spell_id=33076,
            total=200000, overheal_total=20000, overheal_pct=9.1,
        ),
    ]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/overheal/Healer"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["player_name"] == "Healer"
    assert len(data["abilities"]) == 2
    assert data["total_effective"] == 700000
    assert data["total_overheal"] == 120000


async def test_fight_overheal_404(client, mock_session):
    """Returns 404 when no healing data for player."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/overheal/DPS"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/data/reports/{code}/fights/{id}/gear/{player}
# ---------------------------------------------------------------------------

async def test_gear_snapshot_ok(client, mock_session):
    """Returns gear snapshot for a player."""
    mock_row = make_row(slot=0, item_id=12345, item_level=130)
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/gear/Lyro"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["slot"] == 0
    assert data[0]["slot_name"] == "Head"
    assert data[0]["item_level"] == 130


async def test_gear_snapshot_404(client, mock_session):
    """Returns 404 when no gear data for player."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get(
        "/api/data/reports/abc123/fights/1/gear/NoOne"
    )
    assert resp.status_code == 404
