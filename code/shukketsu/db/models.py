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
