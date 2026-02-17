"""Pydantic response models for data API endpoints."""

from pydantic import BaseModel


class ReportSummary(BaseModel):
    code: str
    title: str
    guild_name: str | None
    start_time: int
    end_time: int
    fight_count: int
    boss_count: int


class RaidSummaryFight(BaseModel):
    fight_id: int
    encounter_name: str
    kill: bool
    duration_ms: int
    player_count: int


class ExecutionBoss(BaseModel):
    encounter_name: str
    fight_id: int
    duration_ms: int
    player_count: int
    total_deaths: int | None
    avg_deaths_per_player: float | None
    total_interrupts: int | None
    total_dispels: int | None
    raid_avg_dps: float | None
    raid_total_dps: float | None
    avg_parse: float | None
    avg_ilvl: float | None


class SpeedComparison(BaseModel):
    fight_id: int
    encounter_name: str
    duration_ms: int
    player_count: int
    total_deaths: int | None
    total_interrupts: int | None
    total_dispels: int | None
    avg_dps: float | None
    world_record_ms: int | None
    top10_avg_ms: int | None
    top100_median_ms: int | None


class FightPlayer(BaseModel):
    player_name: str
    player_class: str
    player_spec: str
    dps: float
    hps: float
    parse_percentile: float | None
    deaths: int
    interrupts: int
    dispels: int
    item_level: float | None
    kill: bool
    duration_ms: int
    encounter_name: str
    report_title: str


class RaidComparison(BaseModel):
    encounter_name: str
    a_duration_ms: int | None
    b_duration_ms: int | None
    a_deaths: int | None
    b_deaths: int | None
    a_interrupts: int | None
    b_interrupts: int | None
    a_dispels: int | None
    b_dispels: int | None
    a_avg_dps: float | None
    b_avg_dps: float | None
    a_players: int | None
    b_players: int | None
    a_comp: str | None
    b_comp: str | None


class ProgressionPoint(BaseModel):
    time: str
    best_parse: float | None
    median_parse: float | None
    best_dps: float | None
    median_dps: float | None
    kill_count: int
    avg_deaths: float | None
    encounter_name: str
    character_name: str


class SpecLeaderboardEntry(BaseModel):
    player_class: str
    player_spec: str
    sample_size: int
    avg_dps: float
    max_dps: float
    median_dps: float
    avg_parse: float | None
    avg_ilvl: float | None


class EncounterInfo(BaseModel):
    id: int
    name: str
    zone_id: int
    zone_name: str
    fight_count: int


class CharacterInfo(BaseModel):
    id: int
    name: str
    server_slug: str
    server_region: str
    character_class: str
    spec: str


class RegisterCharacterRequest(BaseModel):
    name: str
    server_slug: str
    server_region: str
    character_class: str
    spec: str


class IngestRequest(BaseModel):
    report_code: str


class IngestResponse(BaseModel):
    report_code: str
    fights: int
    performances: int


class DeathEntry(BaseModel):
    fight_id: int
    encounter_name: str
    player_name: str
    player_class: str
    player_spec: str
    deaths: int
    interrupts: int
    dispels: int


class CharacterReportSummary(BaseModel):
    code: str
    title: str
    guild_name: str | None
    start_time: int
    end_time: int
    fight_count: int
    kill_count: int
    avg_dps: float | None
    avg_parse: float | None
    total_deaths: int | None


class CharacterFightSummary(BaseModel):
    fight_id: int
    encounter_name: str
    kill: bool
    duration_ms: int
    dps: float
    hps: float
    parse_percentile: float | None
    deaths: int
    interrupts: int
    dispels: int
    item_level: float | None
    player_class: str
    player_spec: str
