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
    with_tables: bool = False
    with_events: bool = False


class IngestResponse(BaseModel):
    report_code: str
    fights: int
    performances: int
    table_rows: int = 0
    event_rows: int = 0


class TableDataResponse(BaseModel):
    report_code: str
    table_rows: int


class EventDataResponse(BaseModel):
    report_code: str
    event_rows: int


class RankingsRefreshResponse(BaseModel):
    fetched: int
    skipped: int
    errors: list[str]


class CharacterProfile(BaseModel):
    id: int
    name: str
    server_slug: str
    server_region: str
    character_class: str
    spec: str
    total_fights: int
    total_kills: int
    total_deaths: int
    avg_dps: float | None
    best_dps: float | None
    avg_parse: float | None
    best_parse: float | None
    avg_ilvl: float | None


class CharacterRecentParse(BaseModel):
    encounter_name: str
    dps: float
    hps: float
    parse_percentile: float | None
    deaths: int
    item_level: float | None
    player_class: str
    player_spec: str
    kill: bool
    duration_ms: int
    report_code: str
    fight_id: int
    report_date: int


class DashboardStats(BaseModel):
    total_reports: int
    total_kills: int
    total_wipes: int
    total_characters: int
    total_encounters: int


class RecentReportSummary(BaseModel):
    code: str
    title: str
    guild_name: str | None
    start_time: int
    fight_count: int
    kill_count: int
    wipe_count: int
    avg_kill_dps: float | None


class AbilityMetricResponse(BaseModel):
    player_name: str
    metric_type: str
    ability_name: str
    spell_id: int
    total: int
    hit_count: int
    crit_count: int
    crit_pct: float
    pct_of_total: float


class BuffUptimeResponse(BaseModel):
    player_name: str
    metric_type: str
    ability_name: str
    spell_id: int
    uptime_pct: float
    stack_count: float


class AbilitiesAvailable(BaseModel):
    has_data: bool


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


class DeathDetailResponse(BaseModel):
    player_name: str
    death_index: int
    timestamp_ms: int
    killing_blow_ability: str
    killing_blow_source: str
    damage_taken_total: int
    events_json: str


class CastMetricResponse(BaseModel):
    player_name: str
    total_casts: int
    casts_per_minute: float
    gcd_uptime_pct: float
    active_time_ms: int
    downtime_ms: int
    longest_gap_ms: int
    longest_gap_at_ms: int
    avg_gap_ms: float
    gap_count: int


class CooldownUsageResponse(BaseModel):
    player_name: str
    ability_name: str
    spell_id: int
    cooldown_sec: int
    times_used: int
    max_possible_uses: int
    first_use_ms: int | None
    last_use_ms: int | None
    efficiency_pct: float



class OverhealAbility(BaseModel):
    ability_name: str
    spell_id: int
    total: int
    overheal_total: int
    overheal_pct: float


class OverhealResponse(BaseModel):
    player_name: str
    total_effective: int
    total_overheal: int
    total_overheal_pct: float
    abilities: list[OverhealAbility]


class ConsumableItem(BaseModel):
    category: str
    ability_name: str
    spell_id: int


class ConsumablePlayerEntry(BaseModel):
    player_name: str
    consumables: list[ConsumableItem]
    missing: list[str]


class CancelledCastResponse(BaseModel):
    player_name: str
    total_begins: int
    total_completions: int
    cancel_count: int
    cancel_pct: float
    top_cancelled_json: str | None



class PersonalBestEntry(BaseModel):
    encounter_name: str
    best_dps: float
    best_parse: float | None
    best_hps: float
    kill_count: int
    peak_ilvl: float | None


class WipeProgressionAttempt(BaseModel):
    fight_id: int
    kill: bool
    fight_percentage: float | None
    duration_ms: int
    player_count: int
    avg_dps: float
    total_deaths: int
    avg_parse: float | None


class RegressionEntry(BaseModel):
    player_name: str
    encounter_name: str
    recent_parse: float
    baseline_parse: float
    recent_dps: float
    baseline_dps: float
    parse_delta: float
    dps_delta_pct: float | None


class GearSlotEntry(BaseModel):
    slot: int
    slot_name: str
    item_id: int
    item_level: int


class GearChangeEntry(BaseModel):
    slot: int
    slot_name: str
    old_item_id: int | None
    old_ilvl: int | None
    new_item_id: int | None
    new_ilvl: int | None
    ilvl_delta: int | None


class PhaseInfo(BaseModel):
    name: str
    pct_start: float
    pct_end: float
    estimated_start_ms: int
    estimated_end_ms: int
    estimated_duration_ms: int
    description: str


class PhasePlayerPerformance(BaseModel):
    player_name: str
    player_class: str
    player_spec: str
    dps: float
    total_damage: int
    hps: float
    total_healing: int
    deaths: int
    parse_percentile: float | None


class PhaseAnalysis(BaseModel):
    report_code: str
    fight_id: int
    encounter_name: str
    duration_ms: int
    kill: bool
    phases: list[PhaseInfo]
    players: list[PhasePlayerPerformance]


class AutoIngestStatus(BaseModel):
    enabled: bool
    status: str
    last_poll: str | None
    last_error: str | None
    guild_id: int
    guild_name: str
    poll_interval_minutes: int
    stats: dict


class EventsAvailable(BaseModel):
    has_data: bool


class CastEventResponse(BaseModel):
    player_name: str
    timestamp_ms: int
    spell_id: int
    ability_name: str
    event_type: str
    target_name: str | None


class ResourceSnapshotResponse(BaseModel):
    player_name: str
    resource_type: str
    min_value: int
    max_value: int
    avg_value: float
    time_at_zero_ms: int
    time_at_zero_pct: float
    samples_json: str | None


class DotRefreshResponse(BaseModel):
    player_name: str
    spell_id: int
    ability_name: str
    total_refreshes: int
    early_refreshes: int
    early_refresh_pct: float
    avg_remaining_ms: float
    clipped_ticks_est: float


class RotationScoreResponse(BaseModel):
    player_name: str
    spec: str
    score_pct: float
    rules_checked: int
    rules_passed: int
    violations_json: str | None


class PhaseMetricResponse(BaseModel):
    player_name: str
    phase_name: str
    phase_start_ms: int
    phase_end_ms: int
    is_downtime: bool
    phase_dps: float | None
    phase_casts: int | None
    phase_gcd_uptime_pct: float | None
