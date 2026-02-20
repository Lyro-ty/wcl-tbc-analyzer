import type {
  AbilitiesAvailable,
  AbilityMetric,
  AnalyzeResponse,
  BuffUptime,
  CastEventEntry,
  CastMetricSummary,
  CharacterFightSummary,
  CharacterInfo,
  CharacterReportSummary,
  CooldownUsageEntry,
  DeathDetail,
  EncounterInfo,
  EventsAvailable,
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

export function postAnalyzeStream(
  question: string,
  onToken: (token: string) => void,
  onDone: (queryType: string | null) => void,
  onError: (message: string) => void,
): AbortController {
  const controller = new AbortController()

  ;(async () => {
    try {
      const res = await fetch('/api/analyze/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText)
        onError(`${res.status}: ${detail}`)
        return
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let partial = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        partial += decoder.decode(value, { stream: true })
        const lines = partial.split('\n')
        partial = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          const raw = line.slice(5).trim()
          if (!raw) continue

          try {
            const event = JSON.parse(raw)
            if (event.token) {
              onToken(event.token)
            } else if (event.done) {
              onDone(event.query_type ?? null)
            } else if (event.detail) {
              onError(event.detail)
            }
          } catch {
            // skip malformed SSE lines
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        onError(err instanceof Error ? err.message : 'Stream failed')
      }
    }
  })()

  return controller
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

export async function fetchFightAbilities(code: string, fightId: number): Promise<AbilityMetric[]> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/abilities`)
}

export async function fetchPlayerAbilities(code: string, fightId: number, player: string): Promise<AbilityMetric[]> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/abilities/${encodeURIComponent(player)}`)
}

export async function fetchFightBuffs(code: string, fightId: number): Promise<BuffUptime[]> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/buffs`)
}

export async function fetchPlayerBuffs(code: string, fightId: number, player: string): Promise<BuffUptime[]> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/buffs/${encodeURIComponent(player)}`)
}

export async function fetchAbilitiesAvailable(code: string): Promise<AbilitiesAvailable> {
  return fetchJson(`/api/data/reports/${code}/abilities-available`)
}

export async function fetchFightDeaths(code: string, fightId: number): Promise<DeathDetail[]> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/deaths`)
}

export async function fetchCastMetrics(code: string, fightId: number, player: string): Promise<CastMetricSummary | null> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/cast-metrics/${encodeURIComponent(player)}`)
}

export async function fetchCooldownUsage(code: string, fightId: number, player: string): Promise<CooldownUsageEntry[]> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/cooldowns/${encodeURIComponent(player)}`)
}

export async function fetchResourceUsage(code: string, fightId: number, player: string): Promise<import('./types').ResourceSnapshot[]> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/resources/${encodeURIComponent(player)}`)
}

export async function fetchCancelledCasts(code: string, fightId: number, player: string): Promise<import('./types').CancelledCastSummary | null> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/cancelled-casts/${encodeURIComponent(player)}`)
}

export async function fetchCastTimeline(code: string, fightId: number, player: string): Promise<CastEventEntry[]> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/cast-timeline/${encodeURIComponent(player)}`)
}

export async function fetchOverhealAnalysis(code: string, fightId: number, player: string): Promise<import('./types').OverhealSummary> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/overheal/${encodeURIComponent(player)}`)
}

export async function fetchConsumableCheck(code: string, fightId: number, player: string): Promise<import('./types').ConsumablePlayerEntry | null> {
  const entries: import('./types').ConsumablePlayerEntry[] = await fetchJson(
    `/api/data/reports/${code}/fights/${fightId}/consumables?player=${encodeURIComponent(player)}`
  )
  return entries.length > 0 ? entries[0] : null
}

export async function fetchEventsAvailable(code: string): Promise<EventsAvailable> {
  return fetchJson(`/api/data/reports/${code}/events-available`)
}

export interface EventDataResponse {
  report_code: string
  event_rows: number
}

export async function fetchEventData(code: string): Promise<EventDataResponse> {
  return fetchJson(`/api/data/reports/${code}/event-data`, { method: 'POST' })
}

export interface IngestResponse {
  report_code: string
  fights: number
  performances: number
  table_rows: number
  event_rows: number
}

export async function ingestReport(
  reportCode: string,
  withTables: boolean = false,
  withEvents: boolean = false,
): Promise<IngestResponse> {
  return fetchJson('/api/data/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      report_code: reportCode,
      with_tables: withTables,
      with_events: withEvents,
    }),
  })
}

export interface TableDataResponse {
  report_code: string
  table_rows: number
}

export async function fetchTableData(code: string): Promise<TableDataResponse> {
  return fetchJson(`/api/data/reports/${code}/table-data`, { method: 'POST' })
}

export interface RankingsRefreshResponse {
  fetched: number
  skipped: number
  errors: string[]
}

export async function refreshRankings(zoneId?: number, force?: boolean): Promise<RankingsRefreshResponse> {
  const params = new URLSearchParams()
  if (zoneId != null) params.set('zone_id', String(zoneId))
  if (force) params.set('force', 'true')
  const qs = params.toString()
  return fetchJson(`/api/data/rankings/refresh${qs ? `?${qs}` : ''}`, { method: 'POST' })
}

export async function refreshSpeedRankings(zoneId?: number, force?: boolean): Promise<RankingsRefreshResponse> {
  const params = new URLSearchParams()
  if (zoneId != null) params.set('zone_id', String(zoneId))
  if (force) params.set('force', 'true')
  const qs = params.toString()
  return fetchJson(`/api/data/speed-rankings/refresh${qs ? `?${qs}` : ''}`, { method: 'POST' })
}

export async function getCharacterProfile(name: string): Promise<import('./types').CharacterProfile> {
  return fetchJson(`/api/data/characters/${encodeURIComponent(name)}/profile`)
}

export async function getCharacterRecentParses(name: string): Promise<import('./types').CharacterRecentParse[]> {
  return fetchJson(`/api/data/characters/${encodeURIComponent(name)}/recent-parses`)
}

export async function fetchPhaseMetrics(code: string, fightId: number, player: string): Promise<import('./types').PhaseMetricEntry[]> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/phases/${encodeURIComponent(player)}`)
}

export async function fetchDotRefreshes(
  code: string, fightId: number, player: string,
): Promise<import('./types').DotRefreshEntry[]> {
  return fetchJson(
    `/api/data/reports/${code}/fights/${fightId}/dot-refreshes/${encodeURIComponent(player)}`,
  )
}

export async function fetchRotationScore(
  code: string, fightId: number, player: string,
): Promise<import('./types').RotationScoreEntry | null> {
  return fetchJson(
    `/api/data/reports/${code}/fights/${fightId}/rotation/${encodeURIComponent(player)}`,
  )
}

export async function fetchTrinketProcs(code: string, fightId: number, player: string): Promise<import('./types').TrinketProc[]> {
  return fetchJson(`/api/data/reports/${code}/fights/${fightId}/trinkets/${encodeURIComponent(player)}`)
}

export async function getDashboardStats(): Promise<import('./types').DashboardStats> {
  return fetchJson('/api/data/dashboard/stats')
}

export async function getDashboardRecent(): Promise<import('./types').RecentReportSummary[]> {
  return fetchJson('/api/data/dashboard/recent')
}
