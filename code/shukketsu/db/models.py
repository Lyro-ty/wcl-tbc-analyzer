from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200))
    zone_id: Mapped[int] = mapped_column(Integer)
    zone_name: Mapped[str] = mapped_column(String(200))
    difficulty: Mapped[int] = mapped_column(Integer, default=0)

    fights: Mapped[list["Fight"]] = relationship(back_populates="encounter")
    top_rankings: Mapped[list["TopRanking"]] = relationship(back_populates="encounter")
    speed_rankings: Mapped[list["SpeedRanking"]] = relationship(back_populates="encounter")
    progression_snapshots: Mapped[list["ProgressionSnapshot"]] = relationship(
        back_populates="encounter"
    )


class MyCharacter(Base):
    __tablename__ = "my_characters"
    __table_args__ = (
        UniqueConstraint("name", "server_slug", "server_region"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    server_slug: Mapped[str] = mapped_column(String(100))
    server_region: Mapped[str] = mapped_column(String(10))
    character_class: Mapped[str] = mapped_column(String(50))
    spec: Mapped[str] = mapped_column(String(50))

    progression_snapshots: Mapped[list["ProgressionSnapshot"]] = relationship(
        back_populates="character"
    )


class Report(Base):
    __tablename__ = "reports"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    guild_name: Mapped[str | None] = mapped_column(String(200))
    guild_id: Mapped[int | None] = mapped_column(Integer)
    start_time: Mapped[int] = mapped_column(BigInteger)
    end_time: Mapped[int] = mapped_column(BigInteger)
    fetched_at: Mapped[datetime] = mapped_column(default=func.now())

    fights: Mapped[list["Fight"]] = relationship(back_populates="report")


class Fight(Base):
    __tablename__ = "fights"
    __table_args__ = (
        UniqueConstraint("report_code", "fight_id"),
        Index("ix_fights_report_code", "report_code"),
        Index("ix_fights_encounter_id", "encounter_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_code: Mapped[str] = mapped_column(ForeignKey("reports.code"))
    fight_id: Mapped[int] = mapped_column(Integer)
    encounter_id: Mapped[int] = mapped_column(ForeignKey("encounters.id"))
    start_time: Mapped[int] = mapped_column(BigInteger)
    end_time: Mapped[int] = mapped_column(BigInteger)
    duration_ms: Mapped[int] = mapped_column(
        BigInteger, Computed("end_time - start_time")
    )
    kill: Mapped[bool] = mapped_column(Boolean)
    difficulty: Mapped[int] = mapped_column(Integer, default=0)

    report: Mapped["Report"] = relationship(back_populates="fights")
    encounter: Mapped["Encounter"] = relationship(back_populates="fights")
    performances: Mapped[list["FightPerformance"]] = relationship(back_populates="fight")
    ability_metrics: Mapped[list["AbilityMetric"]] = relationship(back_populates="fight")
    buff_uptimes: Mapped[list["BuffUptime"]] = relationship(back_populates="fight")
    death_details: Mapped[list["DeathDetail"]] = relationship(back_populates="fight")
    cast_metrics: Mapped[list["CastMetric"]] = relationship(back_populates="fight")
    cooldown_usage: Mapped[list["CooldownUsage"]] = relationship(back_populates="fight")
    cancelled_casts: Mapped[list["CancelledCast"]] = relationship(back_populates="fight")
    cast_events: Mapped[list["CastEvent"]] = relationship(back_populates="fight")
    resource_snapshots: Mapped[list["ResourceSnapshot"]] = relationship(
        back_populates="fight"
    )
    cooldown_windows: Mapped[list["CooldownWindow"]] = relationship(
        back_populates="fight"
    )
    phase_metrics: Mapped[list["PhaseMetric"]] = relationship(
        back_populates="fight"
    )
    dot_refreshes: Mapped[list["DotRefresh"]] = relationship(
        back_populates="fight"
    )
    rotation_scores: Mapped[list["RotationScore"]] = relationship(
        back_populates="fight"
    )


class FightPerformance(Base):
    __tablename__ = "fight_performances"
    __table_args__ = (
        Index("ix_fight_performances_fight_id", "fight_id"),
        Index("ix_fight_performances_player_name", "player_name"),
        Index("ix_fight_performances_class_spec", "player_class", "player_spec"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    player_class: Mapped[str] = mapped_column(String(50))
    player_spec: Mapped[str] = mapped_column(String(50))
    player_server: Mapped[str] = mapped_column(String(100))
    total_damage: Mapped[int] = mapped_column(BigInteger, default=0)
    dps: Mapped[float] = mapped_column(Float, default=0.0)
    total_healing: Mapped[int] = mapped_column(BigInteger, default=0)
    hps: Mapped[float] = mapped_column(Float, default=0.0)
    parse_percentile: Mapped[float | None] = mapped_column(Float)
    ilvl_parse_percentile: Mapped[float | None] = mapped_column(Float)
    deaths: Mapped[int] = mapped_column(Integer, default=0)
    interrupts: Mapped[int] = mapped_column(Integer, default=0)
    dispels: Mapped[int] = mapped_column(Integer, default=0)
    item_level: Mapped[float | None] = mapped_column(Float)
    is_my_character: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[datetime] = mapped_column(default=func.now())

    fight: Mapped["Fight"] = relationship(back_populates="performances")


class TopRanking(Base):
    __tablename__ = "top_rankings"
    __table_args__ = (
        Index("ix_top_rankings_encounter_class_spec", "encounter_id", "class", "spec"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    encounter_id: Mapped[int] = mapped_column(ForeignKey("encounters.id"))
    class_: Mapped[str] = mapped_column("class", String(50))
    spec: Mapped[str] = mapped_column(String(50))
    metric: Mapped[str] = mapped_column(String(20))
    rank_position: Mapped[int] = mapped_column(Integer)
    player_name: Mapped[str] = mapped_column(String(100))
    player_server: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Float)
    duration_ms: Mapped[int] = mapped_column(BigInteger)
    report_code: Mapped[str] = mapped_column(String(50))
    fight_id: Mapped[int] = mapped_column(Integer)
    guild_name: Mapped[str | None] = mapped_column(String(200))
    item_level: Mapped[float | None] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(default=func.now())

    encounter: Mapped["Encounter"] = relationship(back_populates="top_rankings")


class SpeedRanking(Base):
    __tablename__ = "speed_rankings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    encounter_id: Mapped[int] = mapped_column(ForeignKey("encounters.id"))
    rank_position: Mapped[int] = mapped_column(Integer)
    report_code: Mapped[str] = mapped_column(String(50))
    fight_id: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(BigInteger)
    guild_name: Mapped[str | None] = mapped_column(String(200))
    fetched_at: Mapped[datetime] = mapped_column(default=func.now())

    encounter: Mapped["Encounter"] = relationship(back_populates="speed_rankings")


class ProgressionSnapshot(Base):
    __tablename__ = "progression_snapshots"

    time: Mapped[datetime] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("my_characters.id"), primary_key=True
    )
    encounter_id: Mapped[int] = mapped_column(
        ForeignKey("encounters.id"), primary_key=True
    )
    best_parse: Mapped[float | None] = mapped_column(Float)
    median_parse: Mapped[float | None] = mapped_column(Float)
    best_dps: Mapped[float | None] = mapped_column(Float)
    median_dps: Mapped[float | None] = mapped_column(Float)
    kill_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_deaths: Mapped[float | None] = mapped_column(Float)

    character: Mapped["MyCharacter"] = relationship(back_populates="progression_snapshots")
    encounter: Mapped["Encounter"] = relationship(back_populates="progression_snapshots")


class AbilityMetric(Base):
    __tablename__ = "ability_metrics"
    __table_args__ = (
        Index("ix_ability_metrics_fight_player", "fight_id", "player_name"),
        Index("ix_ability_metrics_spell_type", "spell_id", "metric_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    metric_type: Mapped[str] = mapped_column(String(20))
    ability_name: Mapped[str] = mapped_column(String(200))
    spell_id: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(BigInteger, default=0)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    crit_count: Mapped[int] = mapped_column(Integer, default=0)
    crit_pct: Mapped[float] = mapped_column(Float, default=0.0)
    pct_of_total: Mapped[float] = mapped_column(Float, default=0.0)
    overheal_total: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    fight: Mapped["Fight"] = relationship(back_populates="ability_metrics")


class BuffUptime(Base):
    __tablename__ = "buff_uptimes"
    __table_args__ = (
        Index("ix_buff_uptimes_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    metric_type: Mapped[str] = mapped_column(String(20))
    ability_name: Mapped[str] = mapped_column(String(200))
    spell_id: Mapped[int] = mapped_column(Integer)
    uptime_pct: Mapped[float] = mapped_column(Float, default=0.0)
    stack_count: Mapped[float] = mapped_column(Float, default=0.0)

    fight: Mapped["Fight"] = relationship(back_populates="buff_uptimes")


class DeathDetail(Base):
    __tablename__ = "death_details"
    __table_args__ = (
        Index("ix_death_details_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    death_index: Mapped[int] = mapped_column(Integer)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)
    killing_blow_ability: Mapped[str] = mapped_column(String(200))
    killing_blow_source: Mapped[str] = mapped_column(String(200))
    damage_taken_total: Mapped[int] = mapped_column(BigInteger, default=0)
    events_json: Mapped[str] = mapped_column(Text)

    fight: Mapped["Fight"] = relationship(back_populates="death_details")


class CastMetric(Base):
    __tablename__ = "cast_metrics"
    __table_args__ = (
        Index("ix_cast_metrics_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    total_casts: Mapped[int] = mapped_column(Integer, default=0)
    casts_per_minute: Mapped[float] = mapped_column(Float, default=0.0)
    gcd_uptime_pct: Mapped[float] = mapped_column(Float, default=0.0)
    active_time_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    downtime_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    longest_gap_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    longest_gap_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    avg_gap_ms: Mapped[float] = mapped_column(Float, default=0.0)
    gap_count: Mapped[int] = mapped_column(Integer, default=0)

    fight: Mapped["Fight"] = relationship(back_populates="cast_metrics")


class CooldownUsage(Base):
    __tablename__ = "cooldown_usage"
    __table_args__ = (
        Index("ix_cooldown_usage_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    spell_id: Mapped[int] = mapped_column(Integer)
    ability_name: Mapped[str] = mapped_column(String(200))
    cooldown_sec: Mapped[int] = mapped_column(Integer)
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    max_possible_uses: Mapped[int] = mapped_column(Integer, default=0)
    first_use_ms: Mapped[int | None] = mapped_column(BigInteger)
    last_use_ms: Mapped[int | None] = mapped_column(BigInteger)
    efficiency_pct: Mapped[float] = mapped_column(Float, default=0.0)

    fight: Mapped["Fight"] = relationship(back_populates="cooldown_usage")


class CancelledCast(Base):
    __tablename__ = "cancelled_casts"
    __table_args__ = (
        Index("ix_cancelled_casts_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    total_begins: Mapped[int] = mapped_column(Integer, default=0)
    total_completions: Mapped[int] = mapped_column(Integer, default=0)
    cancel_count: Mapped[int] = mapped_column(Integer, default=0)
    cancel_pct: Mapped[float] = mapped_column(Float, default=0.0)
    top_cancelled_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    fight: Mapped["Fight"] = relationship(back_populates="cancelled_casts")


class CastEvent(Base):
    __tablename__ = "cast_events"
    __table_args__ = (
        Index(
            "ix_cast_events_fight_player_ts",
            "fight_id", "player_name", "timestamp_ms",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)
    spell_id: Mapped[int] = mapped_column(Integer)
    ability_name: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(20))
    target_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    fight: Mapped["Fight"] = relationship(back_populates="cast_events")


class ResourceSnapshot(Base):
    __tablename__ = "resource_snapshots"
    __table_args__ = (
        Index("ix_resource_snapshots_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(20))
    min_value: Mapped[int] = mapped_column(Integer, default=0)
    max_value: Mapped[int] = mapped_column(Integer, default=0)
    avg_value: Mapped[float] = mapped_column(Float, default=0.0)
    time_at_zero_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    time_at_zero_pct: Mapped[float] = mapped_column(Float, default=0.0)
    samples_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    fight: Mapped["Fight"] = relationship(back_populates="resource_snapshots")


class CooldownWindow(Base):
    __tablename__ = "cooldown_windows"
    __table_args__ = (
        Index("ix_cooldown_windows_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    ability_name: Mapped[str] = mapped_column(String(200))
    spell_id: Mapped[int] = mapped_column(Integer)
    window_start_ms: Mapped[int] = mapped_column(BigInteger)
    window_end_ms: Mapped[int] = mapped_column(BigInteger)
    window_damage: Mapped[int] = mapped_column(BigInteger, default=0)
    window_dps: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_dps: Mapped[float] = mapped_column(Float, default=0.0)
    dps_gain_pct: Mapped[float] = mapped_column(Float, default=0.0)

    fight: Mapped["Fight"] = relationship(back_populates="cooldown_windows")


class PhaseMetric(Base):
    __tablename__ = "phase_metrics"
    __table_args__ = (
        Index("ix_phase_metrics_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    phase_name: Mapped[str] = mapped_column(String(100))
    phase_start_ms: Mapped[int] = mapped_column(BigInteger)
    phase_end_ms: Mapped[int] = mapped_column(BigInteger)
    is_downtime: Mapped[bool] = mapped_column(Boolean, default=False)
    phase_dps: Mapped[float | None] = mapped_column(Float, nullable=True)
    phase_casts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phase_gcd_uptime_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    fight: Mapped["Fight"] = relationship(back_populates="phase_metrics")


class DotRefresh(Base):
    __tablename__ = "dot_refreshes"
    __table_args__ = (
        Index("ix_dot_refreshes_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    spell_id: Mapped[int] = mapped_column(Integer)
    ability_name: Mapped[str] = mapped_column(String(200))
    total_refreshes: Mapped[int] = mapped_column(Integer, default=0)
    early_refreshes: Mapped[int] = mapped_column(Integer, default=0)
    early_refresh_pct: Mapped[float] = mapped_column(Float, default=0.0)
    avg_remaining_ms: Mapped[float] = mapped_column(Float, default=0.0)
    clipped_ticks_est: Mapped[int] = mapped_column(Integer, default=0)

    fight: Mapped["Fight"] = relationship(back_populates="dot_refreshes")


class RotationScore(Base):
    __tablename__ = "rotation_scores"
    __table_args__ = (
        Index("ix_rotation_scores_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    spec: Mapped[str] = mapped_column(String(50))
    score_pct: Mapped[float] = mapped_column(Float, default=0.0)
    rules_checked: Mapped[int] = mapped_column(Integer, default=0)
    rules_passed: Mapped[int] = mapped_column(Integer, default=0)
    violations_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    fight: Mapped["Fight"] = relationship(back_populates="rotation_scores")
