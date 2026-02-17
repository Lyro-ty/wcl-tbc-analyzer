import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from shukketsu.config import Settings
from shukketsu.db.engine import create_db_engine
from shukketsu.db.models import (
    Base,
    CastEvent,
    Encounter,
    Fight,
    FightPerformance,
    MyCharacter,
    ProgressionSnapshot,
    Report,
    ResourceSnapshot,
    TopRanking,
)


class TestModelsInheritBase:
    @pytest.mark.parametrize("model", [
        Encounter, MyCharacter, Report, Fight,
        FightPerformance, TopRanking, ProgressionSnapshot,
        ResourceSnapshot, CastEvent,
    ])
    def test_inherits_base(self, model):
        assert issubclass(model, Base)


class TestTableNames:
    def test_encounter_table(self):
        assert Encounter.__tablename__ == "encounters"

    def test_my_character_table(self):
        assert MyCharacter.__tablename__ == "my_characters"

    def test_report_table(self):
        assert Report.__tablename__ == "reports"

    def test_fight_table(self):
        assert Fight.__tablename__ == "fights"

    def test_fight_performance_table(self):
        assert FightPerformance.__tablename__ == "fight_performances"

    def test_top_ranking_table(self):
        assert TopRanking.__tablename__ == "top_rankings"

    def test_progression_snapshot_table(self):
        assert ProgressionSnapshot.__tablename__ == "progression_snapshots"

    def test_resource_snapshot_table(self):
        assert ResourceSnapshot.__tablename__ == "resource_snapshots"

    def test_cast_event_table(self):
        assert CastEvent.__tablename__ == "cast_events"


class TestColumns:
    def test_encounter_columns(self):
        mapper = inspect(Encounter)
        col_names = {c.key for c in mapper.column_attrs}
        assert {"id", "name", "zone_id", "zone_name", "difficulty"} <= col_names

    def test_my_character_columns(self):
        mapper = inspect(MyCharacter)
        col_names = {c.key for c in mapper.column_attrs}
        assert {"id", "name", "server_slug", "server_region",
                "character_class", "spec"} <= col_names

    def test_report_columns(self):
        mapper = inspect(Report)
        col_names = {c.key for c in mapper.column_attrs}
        assert {"code", "title", "guild_name", "guild_id",
                "start_time", "end_time", "fetched_at"} <= col_names

    def test_fight_columns(self):
        mapper = inspect(Fight)
        col_names = {c.key for c in mapper.column_attrs}
        assert {"id", "report_code", "fight_id", "encounter_id",
                "start_time", "end_time", "duration_ms", "kill",
                "difficulty"} <= col_names

    def test_fight_performance_columns(self):
        mapper = inspect(FightPerformance)
        col_names = {c.key for c in mapper.column_attrs}
        assert {"id", "fight_id", "player_name", "player_class",
                "player_spec", "player_server", "total_damage", "dps",
                "total_healing", "hps", "parse_percentile",
                "ilvl_parse_percentile", "deaths", "interrupts",
                "dispels", "item_level", "is_my_character",
                "fetched_at"} <= col_names

    def test_top_ranking_columns(self):
        mapper = inspect(TopRanking)
        col_names = {c.key for c in mapper.column_attrs}
        assert {"id", "encounter_id", "class_", "spec", "metric",
                "rank_position", "player_name", "player_server",
                "amount", "duration_ms", "report_code", "fight_id",
                "guild_name", "item_level", "fetched_at"} <= col_names

    def test_progression_snapshot_columns(self):
        mapper = inspect(ProgressionSnapshot)
        col_names = {c.key for c in mapper.column_attrs}
        assert {"time", "character_id", "encounter_id", "best_parse",
                "median_parse", "best_dps", "median_dps", "kill_count",
                "avg_deaths"} <= col_names

    def test_resource_snapshot_columns(self):
        mapper = inspect(ResourceSnapshot)
        col_names = {c.key for c in mapper.column_attrs}
        assert {"id", "fight_id", "player_name", "resource_type",
                "min_value", "max_value", "avg_value",
                "time_at_zero_ms", "time_at_zero_pct",
                "samples_json"} <= col_names

    def test_cast_event_columns(self):
        mapper = inspect(CastEvent)
        col_names = {c.key for c in mapper.column_attrs}
        assert {"id", "fight_id", "player_name", "timestamp_ms",
                "spell_id", "ability_name", "event_type",
                "target_name"} <= col_names


class TestConstraints:
    def test_my_character_unique_constraint(self):
        table = MyCharacter.__table__
        unique_constraints = [
            c for c in table.constraints
            if hasattr(c, "columns") and len(c.columns) > 1
        ]
        unique_col_sets = [
            {col.name for col in c.columns} for c in unique_constraints
        ]
        assert {"name", "server_slug", "server_region"} in unique_col_sets

    def test_fight_unique_constraint(self):
        table = Fight.__table__
        unique_constraints = [
            c for c in table.constraints
            if hasattr(c, "columns") and len(c.columns) > 1
        ]
        unique_col_sets = [
            {col.name for col in c.columns} for c in unique_constraints
        ]
        assert {"report_code", "fight_id"} in unique_col_sets

    def test_report_pk_is_code(self):
        table = Report.__table__
        pk_cols = {col.name for col in table.primary_key.columns}
        assert pk_cols == {"code"}


class TestEngine:
    def test_engine_creation(self, monkeypatch):
        monkeypatch.setenv("WCL__CLIENT_ID", "x")
        monkeypatch.setenv("WCL__CLIENT_SECRET", "x")
        settings = Settings()
        engine = create_db_engine(settings)
        assert isinstance(engine, AsyncEngine)
