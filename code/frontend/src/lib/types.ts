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
