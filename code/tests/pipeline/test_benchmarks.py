"""Tests for the benchmark pipeline — discover, ingest, compute."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.pipeline.benchmarks import (
    BenchmarkResult,
    compute_encounter_benchmarks,
    discover_benchmark_reports,
    ingest_benchmark_reports,
    run_benchmark_pipeline,
)


def _make_row(**kwargs):
    """Create a mock DB row with both attribute and _mapping access."""
    ns = SimpleNamespace(**kwargs)
    ns._mapping = kwargs
    return ns


class TestBenchmarkResult:
    def test_defaults(self):
        r = BenchmarkResult()
        assert r.discovered == 0
        assert r.ingested == 0
        assert r.computed == 0
        assert r.errors == []

    def test_custom_values(self):
        r = BenchmarkResult(discovered=5, ingested=3, computed=2, errors=["x"])
        assert r.discovered == 5
        assert r.ingested == 3
        assert r.computed == 2
        assert r.errors == ["x"]

    def test_errors_list_independence(self):
        """Each instance gets its own errors list."""
        a = BenchmarkResult()
        b = BenchmarkResult()
        a.errors.append("a_error")
        assert b.errors == []


class TestDiscoverBenchmarkReports:
    async def test_returns_new_reports(self):
        session = AsyncMock()

        # Speed ranking rows
        speed_rows = [
            _make_row(report_code="abc", encounter_id=650, guild_name="Guild A"),
            _make_row(report_code="def", encounter_id=650, guild_name="Guild B"),
            _make_row(report_code="ghi", encounter_id=649, guild_name="Guild C"),
        ]
        # Existing benchmark codes
        existing_rows = [_make_row(report_code="abc")]
        # No watched guilds
        watched_mock = MagicMock()
        watched_mock.scalars.return_value.all.return_value = []

        speed_result = MagicMock()
        speed_result.fetchall.return_value = speed_rows
        existing_result = MagicMock()
        existing_result.fetchall.return_value = existing_rows

        session.execute = AsyncMock(
            side_effect=[speed_result, watched_mock, existing_result]
        )

        reports = await discover_benchmark_reports(session, encounter_id=None)

        assert len(reports) == 2
        codes = {r["report_code"] for r in reports}
        assert codes == {"def", "ghi"}
        assert all(r["source"] == "speed_ranking" for r in reports)

    async def test_limits_per_encounter(self):
        session = AsyncMock()

        # 5 codes for encounter 650
        speed_rows = [
            _make_row(
                report_code=f"code{i}", encounter_id=650, guild_name=f"G{i}"
            )
            for i in range(5)
        ]
        speed_result = MagicMock()
        speed_result.fetchall.return_value = speed_rows

        existing_result = MagicMock()
        existing_result.fetchall.return_value = []

        watched_mock = MagicMock()
        watched_mock.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(
            side_effect=[speed_result, watched_mock, existing_result]
        )

        reports = await discover_benchmark_reports(
            session, encounter_id=650, max_per_encounter=3,
        )

        assert len(reports) == 3

    async def test_filters_existing_codes(self):
        session = AsyncMock()

        speed_rows = [
            _make_row(report_code="abc", encounter_id=650, guild_name="G1"),
        ]
        existing_rows = [_make_row(report_code="abc")]

        speed_result = MagicMock()
        speed_result.fetchall.return_value = speed_rows
        existing_result = MagicMock()
        existing_result.fetchall.return_value = existing_rows

        watched_mock = MagicMock()
        watched_mock.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(
            side_effect=[speed_result, watched_mock, existing_result]
        )

        reports = await discover_benchmark_reports(session)

        assert len(reports) == 0

    async def test_deduplicates_across_encounters(self):
        """Same report_code for different encounters only appears once."""
        session = AsyncMock()

        # Same report for two encounters (e.g. Gruul + Mag in same report)
        speed_rows = [
            _make_row(report_code="abc", encounter_id=650, guild_name="G1"),
            _make_row(report_code="abc", encounter_id=649, guild_name="G1"),
            _make_row(report_code="def", encounter_id=650, guild_name="G2"),
        ]
        speed_result = MagicMock()
        speed_result.fetchall.return_value = speed_rows
        existing_result = MagicMock()
        existing_result.fetchall.return_value = []
        watched_mock = MagicMock()
        watched_mock.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(
            side_effect=[speed_result, watched_mock, existing_result]
        )

        reports = await discover_benchmark_reports(session)

        # "abc" should only appear once (first encounter wins)
        assert len(reports) == 2
        codes = [r["report_code"] for r in reports]
        assert codes == ["abc", "def"]
        # First appearance is encounter 650
        assert reports[0]["encounter_id"] == 650


def _mock_session_with_savepoints():
    """Create an AsyncMock session that supports begin_nested() as async cm."""
    session = AsyncMock()
    session.add = MagicMock()  # sync method on AsyncSession

    @asynccontextmanager
    async def _begin_nested():
        yield

    session.begin_nested = _begin_nested
    return session


class TestIngestBenchmarkReports:
    async def test_ingests_reports(self):
        wcl = AsyncMock()
        session = _mock_session_with_savepoints()

        reports = [
            {
                "report_code": "abc",
                "source": "speed_ranking",
                "encounter_id": 650,
                "guild_name": "Top Guild",
            },
            {
                "report_code": "def",
                "source": "speed_ranking",
                "encounter_id": 649,
                "guild_name": None,
            },
        ]

        with patch(
            "shukketsu.pipeline.benchmarks.ingest_report",
            new_callable=AsyncMock,
        ) as mock_ingest:
            result = await ingest_benchmark_reports(wcl, session, reports)

        assert result == {"ingested": 2, "errors": 0}
        assert mock_ingest.call_count == 2
        # session.add() is sync on AsyncSession
        assert session.add.call_count == 2
        assert session.commit.call_count == 2

        # Verify ingest_report called with correct args
        first_call = mock_ingest.call_args_list[0]
        assert first_call.args == (wcl, session, "abc")
        assert first_call.kwargs == {"ingest_tables": True, "ingest_events": True}

    async def test_handles_ingest_error(self):
        wcl = AsyncMock()
        session = _mock_session_with_savepoints()

        reports = [
            {
                "report_code": "abc",
                "source": "speed_ranking",
                "encounter_id": 650,
                "guild_name": "G1",
            },
            {
                "report_code": "fail",
                "source": "speed_ranking",
                "encounter_id": 649,
                "guild_name": "G2",
            },
        ]

        async def mock_ingest(wcl_, session_, code, **kwargs):
            if code == "fail":
                raise RuntimeError("WCL API error")

        with patch(
            "shukketsu.pipeline.benchmarks.ingest_report",
            side_effect=mock_ingest,
        ):
            result = await ingest_benchmark_reports(wcl, session, reports)

        assert result == {"ingested": 1, "errors": 1}
        assert session.rollback.call_count == 1

    async def test_duplicate_code_raises_on_second_add(self):
        """Same report_code twice would fail on unique constraint.

        In practice, discover_benchmark_reports deduplicates upstream via
        seen_codes set. This test shows that if duplicates slip through,
        the second add raises (caught by the error handler).
        """
        wcl = AsyncMock()
        session = _mock_session_with_savepoints()
        # Second commit raises unique violation
        session.commit = AsyncMock(
            side_effect=[None, Exception("unique violation")]
        )

        reports = [
            {
                "report_code": "abc",
                "source": "speed_ranking",
                "encounter_id": 650,
                "guild_name": "G1",
            },
            {
                "report_code": "abc",
                "source": "speed_ranking",
                "encounter_id": 649,
                "guild_name": "G1",
            },
        ]

        with patch(
            "shukketsu.pipeline.benchmarks.ingest_report",
            new_callable=AsyncMock,
        ):
            result = await ingest_benchmark_reports(wcl, session, reports)

        assert result == {"ingested": 1, "errors": 1}
        assert session.rollback.call_count == 1

    async def test_empty_reports(self):
        wcl = AsyncMock()
        session = AsyncMock()

        result = await ingest_benchmark_reports(wcl, session, [])

        assert result == {"ingested": 0, "errors": 0}


class TestComputeEncounterBenchmarks:
    async def test_computes_benchmarks(self):
        session = AsyncMock()
        # session.merge() is async on AsyncSession — leave as AsyncMock

        # Mock results for all 9 aggregation queries
        kill_rows = [_make_row(
            encounter_id=650,
            kill_count=10,
            avg_duration_ms=120000,
            median_duration_ms=118000,
            min_duration_ms=95000,
        )]
        death_rows = [_make_row(
            encounter_id=650,
            avg_deaths=0.5,
            zero_death_pct=60.0,
        )]
        spec_dps_rows = [_make_row(
            encounter_id=650,
            player_class="Warrior",
            player_spec="Arms",
            sample_size=5,
            avg_dps=1500.0,
            median_dps=1480.0,
            p75_dps=1550.0,
            avg_hps=0.0,
            median_hps=0.0,
            p75_hps=0.0,
        )]
        spec_gcd_rows = [_make_row(
            encounter_id=650,
            player_class="Warrior",
            player_spec="Arms",
            avg_gcd_uptime=85.0,
            avg_cpm=30.0,
        )]
        ability_rows = [_make_row(
            encounter_id=650,
            player_class="Warrior",
            player_spec="Arms",
            ability_name="Mortal Strike",
            avg_damage_pct=25.0,
        )]
        buff_rows = [_make_row(
            encounter_id=650,
            player_class="Warrior",
            player_spec="Arms",
            buff_name="Battle Shout",
            avg_uptime=90.0,
        )]
        cooldown_rows = [_make_row(
            encounter_id=650,
            player_class="Warrior",
            player_spec="Arms",
            ability_name="Recklessness",
            avg_uses=1.5,
            avg_efficiency=75.0,
        )]
        consumable_rows = [_make_row(
            category="flask",
            usage_pct=95.0,
            players_with=19,
            total_player_fights=20,
        )]
        composition_rows = [_make_row(
            encounter_id=650,
            player_class="Warrior",
            player_spec="Arms",
            avg_count=2.5,
        )]

        # Build mock results in order: kill, death, spec_dps, spec_gcd,
        # abilities, buffs, cooldowns, consumables, composition
        mock_results = []
        for rows in [
            kill_rows, death_rows, spec_dps_rows, spec_gcd_rows,
            ability_rows, buff_rows, cooldown_rows,
            consumable_rows, composition_rows,
        ]:
            mock_result = MagicMock()
            mock_result.fetchall.return_value = rows
            mock_results.append(mock_result)

        session.execute = AsyncMock(side_effect=mock_results)

        result = await compute_encounter_benchmarks(session, encounter_id=650)

        assert result == {"computed": 1}
        assert session.merge.await_count == 1
        assert session.commit.await_count == 1

        # Verify the merged EncounterBenchmark structure
        merged_obj = session.merge.call_args[0][0]
        assert merged_obj.encounter_id == 650
        assert merged_obj.sample_size == 10

        benchmarks = merged_obj.benchmarks
        assert benchmarks["kill_stats"]["kill_count"] == 10
        assert benchmarks["kill_stats"]["avg_duration_ms"] == 120000.0
        assert benchmarks["kill_stats"]["median_duration_ms"] == 118000.0
        assert benchmarks["kill_stats"]["min_duration_ms"] == 95000

        assert benchmarks["deaths"]["avg_deaths"] == 0.5
        assert benchmarks["deaths"]["zero_death_pct"] == 60.0

        # Check by_spec
        assert "Arms Warrior" in benchmarks["by_spec"]
        arms = benchmarks["by_spec"]["Arms Warrior"]
        assert arms["dps"]["avg_dps"] == 1500.0
        assert arms["dps"]["median_dps"] == 1480.0
        assert arms["gcd"]["avg_gcd_uptime"] == 85.0
        assert arms["gcd"]["avg_cpm"] == 30.0
        assert len(arms["abilities"]) == 1
        assert arms["abilities"][0]["ability_name"] == "Mortal Strike"
        assert len(arms["buffs"]) == 1
        assert arms["buffs"][0]["buff_name"] == "Battle Shout"
        assert len(arms["cooldowns"]) == 1
        assert arms["cooldowns"][0]["ability_name"] == "Recklessness"

        assert benchmarks["consumables"][0]["category"] == "flask"
        assert benchmarks["consumables"][0]["usage_pct"] == 95.0

        assert len(benchmarks["composition"]) == 1
        assert benchmarks["composition"][0]["class"] == "Warrior"

    async def test_no_kill_rows(self):
        session = AsyncMock()
        # session.merge() is async on AsyncSession — leave as AsyncMock

        # All queries return empty results
        mock_results = []
        for _ in range(9):
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_results.append(mock_result)

        session.execute = AsyncMock(side_effect=mock_results)

        result = await compute_encounter_benchmarks(session)

        assert result == {"computed": 0}
        assert session.merge.await_count == 0

    async def test_multiple_encounters(self):
        session = AsyncMock()
        # session.merge() is async on AsyncSession — leave as AsyncMock

        kill_rows = [
            _make_row(
                encounter_id=649, kill_count=8,
                avg_duration_ms=110000, median_duration_ms=108000,
                min_duration_ms=90000,
            ),
            _make_row(
                encounter_id=650, kill_count=12,
                avg_duration_ms=130000, median_duration_ms=128000,
                min_duration_ms=100000,
            ),
        ]
        # Empty supplementary data for simplicity
        mock_results = [MagicMock() for _ in range(9)]
        mock_results[0].fetchall.return_value = kill_rows
        for i in range(1, 9):
            mock_results[i].fetchall.return_value = []

        session.execute = AsyncMock(side_effect=mock_results)

        result = await compute_encounter_benchmarks(session)

        assert result == {"computed": 2}
        assert session.merge.await_count == 2


class TestRunBenchmarkPipeline:
    async def test_full_pipeline(self):
        wcl = AsyncMock()
        session = AsyncMock()

        discovered_reports = [
            {
                "report_code": "abc",
                "source": "speed_ranking",
                "encounter_id": 650,
                "guild_name": "G1",
            },
        ]

        with (
            patch(
                "shukketsu.pipeline.benchmarks.discover_benchmark_reports",
                new_callable=AsyncMock,
                return_value=discovered_reports,
            ) as mock_discover,
            patch(
                "shukketsu.pipeline.benchmarks.ingest_benchmark_reports",
                new_callable=AsyncMock,
                return_value={"ingested": 1, "errors": 0},
            ) as mock_ingest,
            patch(
                "shukketsu.pipeline.benchmarks.compute_encounter_benchmarks",
                new_callable=AsyncMock,
                return_value={"computed": 1},
            ) as mock_compute,
        ):
            result = await run_benchmark_pipeline(wcl, session)

        assert result.discovered == 1
        assert result.ingested == 1
        assert result.computed == 1
        assert result.errors == []

        mock_discover.assert_called_once_with(
            session, encounter_id=None, max_per_encounter=10,
        )
        mock_ingest.assert_called_once_with(wcl, session, discovered_reports)
        mock_compute.assert_called_once_with(session, encounter_id=None)

    async def test_compute_only(self):
        wcl = AsyncMock()
        session = AsyncMock()

        with (
            patch(
                "shukketsu.pipeline.benchmarks.discover_benchmark_reports",
                new_callable=AsyncMock,
            ) as mock_discover,
            patch(
                "shukketsu.pipeline.benchmarks.ingest_benchmark_reports",
                new_callable=AsyncMock,
            ) as mock_ingest,
            patch(
                "shukketsu.pipeline.benchmarks.compute_encounter_benchmarks",
                new_callable=AsyncMock,
                return_value={"computed": 3},
            ),
        ):
            result = await run_benchmark_pipeline(
                wcl, session, compute_only=True,
            )

        assert result.discovered == 0
        assert result.ingested == 0
        assert result.computed == 3
        mock_discover.assert_not_called()
        mock_ingest.assert_not_called()

    async def test_with_encounter_filter(self):
        wcl = AsyncMock()
        session = AsyncMock()

        with (
            patch(
                "shukketsu.pipeline.benchmarks.discover_benchmark_reports",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_discover,
            patch(
                "shukketsu.pipeline.benchmarks.ingest_benchmark_reports",
                new_callable=AsyncMock,
            ) as mock_ingest,
            patch(
                "shukketsu.pipeline.benchmarks.compute_encounter_benchmarks",
                new_callable=AsyncMock,
                return_value={"computed": 1},
            ) as mock_compute,
        ):
            result = await run_benchmark_pipeline(
                wcl, session, encounter_id=650, max_reports_per_encounter=5,
            )

        assert result.discovered == 0
        assert result.computed == 1

        mock_discover.assert_called_once_with(
            session, encounter_id=650, max_per_encounter=5,
        )
        # No reports discovered, so ingest should not be called
        mock_ingest.assert_not_called()
        mock_compute.assert_called_once_with(session, encounter_id=650)

    async def test_ingest_errors_tracked(self):
        wcl = AsyncMock()
        session = AsyncMock()

        with (
            patch(
                "shukketsu.pipeline.benchmarks.discover_benchmark_reports",
                new_callable=AsyncMock,
                return_value=[{"report_code": "x", "source": "s"}],
            ),
            patch(
                "shukketsu.pipeline.benchmarks.ingest_benchmark_reports",
                new_callable=AsyncMock,
                return_value={"ingested": 0, "errors": 1},
            ),
            patch(
                "shukketsu.pipeline.benchmarks.compute_encounter_benchmarks",
                new_callable=AsyncMock,
                return_value={"computed": 0},
            ),
        ):
            result = await run_benchmark_pipeline(wcl, session)

        assert result.ingested == 0
        assert len(result.errors) == 1
        assert "1 reports failed" in result.errors[0]
