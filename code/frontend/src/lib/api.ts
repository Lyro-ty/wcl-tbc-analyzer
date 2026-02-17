import type {
  AnalyzeResponse,
  CharacterFightSummary,
  CharacterInfo,
  CharacterReportSummary,
  EncounterInfo,
  ExecutionBoss,
  FightPlayer,
  ProgressionPoint,
  RaidComparison,
  RaidSummaryFight,
  ReportSummary,
  SpecLeaderboardEntry,
  SpeedComparison,
} from './types'

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export async function postAnalyze(question: string): Promise<AnalyzeResponse> {
  return fetchJson<AnalyzeResponse>('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
}

export async function getReports(): Promise<ReportSummary[]> {
  return fetchJson('/api/data/reports')
}

export async function getReportSummary(code: string): Promise<RaidSummaryFight[]> {
  return fetchJson(`/api/data/reports/${code}/summary`)
}

export async function getReportExecution(code: string): Promise<ExecutionBoss[]> {
  return fetchJson(`/api/data/reports/${code}/execution`)
}

export async function getReportSpeed(code: string): Promise<SpeedComparison[]> {
  return fetchJson(`/api/data/reports/${code}/speed`)
}

export async function getFightDetails(code: string, fightId: number): Promise<FightPlayer[]> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}`)
}

export async function compareRaids(a: string, b: string): Promise<RaidComparison[]> {
  return fetchJson(`/api/data/compare?a=${a}&b=${b}`)
}

export async function getProgression(character: string, encounter: string): Promise<ProgressionPoint[]> {
  return fetchJson(`/api/data/progression/${encodeURIComponent(character)}?encounter=${encodeURIComponent(encounter)}`)
}

export async function getLeaderboard(encounter: string): Promise<SpecLeaderboardEntry[]> {
  return fetchJson(`/api/data/leaderboard/${encodeURIComponent(encounter)}`)
}

export async function getEncounters(): Promise<EncounterInfo[]> {
  return fetchJson('/api/data/encounters')
}

export async function getCharacters(): Promise<CharacterInfo[]> {
  return fetchJson('/api/data/characters')
}

export async function getCharacterReports(name: string): Promise<CharacterReportSummary[]> {
  return fetchJson(`/api/data/characters/${encodeURIComponent(name)}/reports`)
}

export async function getCharacterReportDetail(name: string, code: string): Promise<CharacterFightSummary[]> {
  return fetchJson(`/api/data/characters/${encodeURIComponent(name)}/reports/${encodeURIComponent(code)}`)
}

export async function registerCharacter(data: {
  name: string
  server_slug: string
  server_region: string
  character_class: string
  spec: string
}): Promise<CharacterInfo> {
  return fetchJson('/api/data/characters', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export interface IngestResponse {
  report_code: string
  fights: number
  performances: number
}

export async function ingestReport(reportCode: string): Promise<IngestResponse> {
  return fetchJson('/api/data/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_code: reportCode }),
  })
}
