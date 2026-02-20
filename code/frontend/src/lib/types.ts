export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  queryType?: string | null
  timestamp: number
}

export interface AnalyzeResponse {
  answer: string
  query_type: string | null
}

export interface ReportSummary {
  code: string
  title: string
  guild_name: string | null
  start_time: number
  end_time: number
  fight_count: number
  boss_count: number
}

export interface RaidSummaryFight {
  fight_id: number
  encounter_name: string
  kill: boolean
  duration_ms: number
  player_count: number
}

export interface ExecutionBoss {
  encounter_name: string
  fight_id: number
  duration_ms: number
  player_count: number
  total_deaths: number | null
  avg_deaths_per_player: number | null
  total_interrupts: number | null
  total_dispels: number | null
  raid_avg_dps: number | null
  raid_total_dps: number | null
  avg_parse: number | null
  avg_ilvl: number | null
}

export interface SpeedComparison {
  fight_id: number
  encounter_name: string
  duration_ms: number
  player_count: number
  total_deaths: number | null
  total_interrupts: number | null
  total_dispels: number | null
  avg_dps: number | null
  world_record_ms: number | null
  top10_avg_ms: number | null
  top100_median_ms: number | null
}

export interface FightPlayer {
  player_name: string
  player_class: string
  player_spec: string
  dps: number
  hps: number
  parse_percentile: number | null
  deaths: number
  interrupts: number
  dispels: number
  item_level: number | null
  kill: boolean
  duration_ms: number
  encounter_name: string
  report_title: string
}

export interface RaidComparison {
  encounter_name: string
  a_duration_ms: number | null
  b_duration_ms: number | null
  a_deaths: number | null
  b_deaths: number | null
  a_interrupts: number | null
  b_interrupts: number | null
  a_dispels: number | null
  b_dispels: number | null
  a_avg_dps: number | null
  b_avg_dps: number | null
  a_players: number | null
  b_players: number | null
  a_comp: string | null
  b_comp: string | null
}

export interface ProgressionPoint {
  time: string
  best_parse: number | null
  median_parse: number | null
  best_dps: number | null
  median_dps: number | null
  kill_count: number
  avg_deaths: number | null
  encounter_name: string
  character_name: string
}

export interface SpecLeaderboardEntry {
  player_class: string
  player_spec: string
  sample_size: number
  avg_dps: number
  max_dps: number
  median_dps: number
  avg_parse: number | null
  avg_ilvl: number | null
}

export interface EncounterInfo {
  id: number
  name: string
  zone_id: number
  zone_name: string
  fight_count: number
}

export interface CharacterInfo {
  id: number
  name: string
  server_slug: string
  server_region: string
  character_class: string
  spec: string
}

export interface CharacterReportSummary {
  code: string
  title: string
  guild_name: string | null
  start_time: number
  end_time: number
  fight_count: number
  kill_count: number
  avg_dps: number | null
  avg_parse: number | null
  total_deaths: number | null
}

export interface CharacterFightSummary {
  fight_id: number
  encounter_name: string
  kill: boolean
  duration_ms: number
  dps: number
  hps: number
  parse_percentile: number | null
  deaths: number
  interrupts: number
  dispels: number
  item_level: number | null
  player_class: string
  player_spec: string
}

export interface AbilityMetric {
  player_name: string
  metric_type: string
  ability_name: string
  spell_id: number
  total: number
  hit_count: number
  crit_count: number
  crit_pct: number
  pct_of_total: number
}

export interface BuffUptime {
  player_name: string
  metric_type: string
  ability_name: string
  spell_id: number
  uptime_pct: number
  stack_count: number
}

export interface AbilitiesAvailable {
  has_data: boolean
}

export interface CharacterProfile {
  id: number
  name: string
  server_slug: string
  server_region: string
  character_class: string
  spec: string
  total_fights: number
  total_kills: number
  total_deaths: number
  avg_dps: number | null
  best_dps: number | null
  avg_parse: number | null
  best_parse: number | null
  avg_ilvl: number | null
}

export interface CharacterRecentParse {
  encounter_name: string
  dps: number
  hps: number
  parse_percentile: number | null
  deaths: number
  item_level: number | null
  player_class: string
  player_spec: string
  kill: boolean
  duration_ms: number
  report_code: string
  fight_id: number
  report_date: number
}

export interface DeathDetail {
  player_name: string
  death_index: number
  timestamp_ms: number
  killing_blow_ability: string
  killing_blow_source: string
  damage_taken_total: number
  events_json: string
}

export interface CastMetricSummary {
  player_name: string
  total_casts: number
  casts_per_minute: number
  gcd_uptime_pct: number
  active_time_ms: number
  downtime_ms: number
  longest_gap_ms: number
  longest_gap_at_ms: number
  avg_gap_ms: number
  gap_count: number
}

export interface CooldownUsageEntry {
  player_name: string
  ability_name: string
  spell_id: number
  cooldown_sec: number
  times_used: number
  max_possible_uses: number
  first_use_ms: number | null
  last_use_ms: number | null
  efficiency_pct: number
}

export interface EventsAvailable {
  has_data: boolean
}

export interface OverhealAbility {
  ability_name: string
  spell_id: number
  total: number
  overheal_total: number
  overheal_pct: number
}

export interface OverhealSummary {
  player_name: string
  total_effective: number
  total_overheal: number
  total_overheal_pct: number
  abilities: OverhealAbility[]
}

export interface ConsumableItem {
  category: string
  ability_name: string
  spell_id: number
}

export interface ConsumablePlayerEntry {
  player_name: string
  consumables: ConsumableItem[]
  missing: string[]
}

export interface CancelledCastSummary {
  player_name: string
  total_begins: number
  total_completions: number
  cancel_count: number
  cancel_pct: number
  top_cancelled_json: string | null
}

export interface CastEventEntry {
  player_name: string
  timestamp_ms: number
  spell_id: number
  ability_name: string
  event_type: string
  target_name: string | null
}

export interface ResourceSnapshot {
  player_name: string
  resource_type: string
  min_value: number
  max_value: number
  avg_value: number
  time_at_zero_ms: number
  time_at_zero_pct: number
  samples_json: string | null
}

export interface PhaseMetricEntry {
  player_name: string
  phase_name: string
  phase_start_ms: number
  phase_end_ms: number
  is_downtime: boolean
  phase_dps: number | null
  phase_casts: number | null
  phase_gcd_uptime_pct: number | null
}

export interface DotRefreshEntry {
  player_name: string
  spell_id: number
  ability_name: string
  total_refreshes: number
  early_refreshes: number
  early_refresh_pct: number
  avg_remaining_ms: number
  clipped_ticks_est: number
}

export interface RotationScoreEntry {
  player_name: string
  spec: string
  score_pct: number
  rules_checked: number
  rules_passed: number
  violations_json: string | null
}

export interface DashboardStats {
  total_reports: number
  total_kills: number
  total_wipes: number
  total_characters: number
  total_encounters: number
}

export interface RecentReportSummary {
  code: string
  title: string
  guild_name: string | null
  start_time: number
  fight_count: number
  kill_count: number
  wipe_count: number
  avg_kill_dps: number | null
}
