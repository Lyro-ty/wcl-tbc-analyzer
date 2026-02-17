import { useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ArrowLeft, Database, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  fetchAbilitiesAvailable,
  fetchTableData,
  getFightDetails,
  getReportExecution,
  getReportSpeed,
  getReportSummary,
} from '../lib/api'
import type { FightPlayer } from '../lib/types'
import { useApiQuery } from '../hooks/useApiQuery'
import BossCard from '../components/ui/BossCard'
import DataTable, { type Column } from '../components/ui/DataTable'
import QuickAction from '../components/ui/QuickAction'
import ErrorBoundary from '../components/ui/ErrorBoundary'
import SpeedComparisonChart from '../components/charts/SpeedComparisonChart'
import { classColor, formatDuration, formatNumber, parseColor } from '../lib/wow-classes'

export default function ReportDetailPage() {
  const { code } = useParams<{ code: string }>()
  const [expandedFight, setExpandedFight] = useState<number | null>(null)
  const [fightPlayers, setFightPlayers] = useState<FightPlayer[]>([])
  const [loadingFight, setLoadingFight] = useState(false)
  const [fetchingTable, setFetchingTable] = useState(false)
  const [fetchTableError, setFetchTableError] = useState<string | null>(null)

  const { data: summary, loading: loadSummary } = useApiQuery(
    () => getReportSummary(code!), [code],
  )
  const { data: execution } = useApiQuery(
    () => getReportExecution(code!), [code],
  )
  const { data: speed } = useApiQuery(
    () => getReportSpeed(code!), [code],
  )
  const { data: abilitiesAvail, refetch: refetchAbilities } = useApiQuery(
    () => fetchAbilitiesAvailable(code!), [code],
  )

  const handleFetchTableData = useCallback(async () => {
    setFetchingTable(true)
    setFetchTableError(null)
    try {
      await fetchTableData(code!)
      refetchAbilities()
    } catch (err) {
      setFetchTableError(err instanceof Error ? err.message : 'Failed to fetch table data')
    } finally {
      setFetchingTable(false)
    }
  }, [code, refetchAbilities])

  const [fightError, setFightError] = useState<string | null>(null)

  const toggleFight = useCallback(async (fightId: number) => {
    if (expandedFight === fightId) {
      setExpandedFight(null)
      return
    }
    setExpandedFight(fightId)
    setLoadingFight(true)
    setFightError(null)
    try {
      const players = await getFightDetails(code!, fightId)
      setFightPlayers(players)
    } catch (err) {
      setFightPlayers([])
      setFightError(err instanceof Error ? err.message : 'Failed to load fight details')
    } finally {
      setLoadingFight(false)
    }
  }, [code, expandedFight])

  const playerColumns: Column<FightPlayer>[] = [
    { key: 'name', label: 'Player', render: (r) => (
      expandedFight ? (
        <Link
          to={`/reports/${code}/fights/${expandedFight}/player/${encodeURIComponent(r.player_name)}`}
          className="underline decoration-zinc-700 underline-offset-2 hover:decoration-zinc-400"
          style={{ color: classColor(r.player_class) }}
        >
          {r.player_name}
        </Link>
      ) : (
        <span style={{ color: classColor(r.player_class) }}>{r.player_name}</span>
      )
    )},
    { key: 'spec', label: 'Spec', render: (r) => (
      <span className="text-zinc-400">{r.player_spec} {r.player_class}</span>
    )},
    { key: 'dps', label: 'DPS', sortValue: (r) => r.dps, render: (r) => formatNumber(r.dps) },
    { key: 'parse', label: 'Parse', sortValue: (r) => r.parse_percentile ?? 0, render: (r) => (
      <span className={parseColor(r.parse_percentile)}>
        {r.parse_percentile != null ? `${r.parse_percentile}%` : '—'}
      </span>
    )},
    { key: 'deaths', label: 'Deaths', sortValue: (r) => r.deaths, render: (r) => (
      <span className={r.deaths > 0 ? 'text-red-400' : ''}>{r.deaths}</span>
    )},
    { key: 'interrupts', label: 'Int', sortValue: (r) => r.interrupts, render: (r) => r.interrupts },
    { key: 'dispels', label: 'Disp', sortValue: (r) => r.dispels, render: (r) => r.dispels },
  ]

  if (loadSummary) {
    return (
      <div className="space-y-3">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-32 animate-pulse rounded-lg bg-zinc-800/50" />
        ))}
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        <Link to="/reports" className="text-zinc-400 hover:text-zinc-200">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <h1 className="text-2xl font-bold">Report {code}</h1>
        <QuickAction question={`Analyze our raid in report ${code}`} />
      </div>

      {/* Speed chart */}
      {speed && speed.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 text-lg font-semibold text-zinc-200">Kill Speed vs Top Rankings</h2>
          <ErrorBoundary>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
              <SpeedComparisonChart data={speed} />
            </div>
          </ErrorBoundary>
        </div>
      )}

      {/* Table data callout */}
      {abilitiesAvail && !abilitiesAvail.has_data && (
        <div className="mb-6 flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/30 px-5 py-4">
          <div>
            <p className="text-sm font-medium text-zinc-300">
              Ability &amp; buff data not yet fetched for this report
            </p>
            <p className="text-xs text-zinc-500">
              Fetch table data to see per-ability breakdowns and buff uptimes per player.
            </p>
          </div>
          <button
            onClick={handleFetchTableData}
            disabled={fetchingTable}
            className="inline-flex items-center gap-2 rounded-lg bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-zinc-700 disabled:opacity-50"
          >
            {fetchingTable ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Fetching...</>
            ) : (
              <><Database className="h-4 w-4" /> Fetch Ability &amp; Buff Data</>
            )}
          </button>
        </div>
      )}
      {fetchTableError && (
        <div className="mb-6 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {fetchTableError}
        </div>
      )}

      {/* Boss grid */}
      <h2 className="mb-4 text-lg font-semibold text-zinc-200">Boss Fights</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {summary?.map((fight) => {
          const exec = execution?.find((e) => e.fight_id === fight.fight_id)
          return (
            <div key={fight.fight_id}>
              <BossCard
                name={fight.encounter_name}
                kill={fight.kill}
                durationMs={fight.duration_ms}
                deaths={exec?.total_deaths}
                avgDps={exec?.raid_avg_dps}
                playerCount={fight.player_count}
                onClick={() => toggleFight(fight.fight_id)}
              >
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-xs text-zinc-500">
                    {fight.kill ? '✓ Kill' : '✗ Wipe'} &middot; {formatDuration(fight.duration_ms)}
                  </span>
                  <QuickAction question={`How did we do on ${fight.encounter_name} in ${code}?`} />
                </div>
              </BossCard>
              {expandedFight === fight.fight_id && (
                <div className="mt-2">
                  {loadingFight ? (
                    <div className="flex items-center gap-2 p-4 text-sm text-zinc-400">
                      <Loader2 className="h-4 w-4 animate-spin" /> Loading roster...
                    </div>
                  ) : fightError ? (
                    <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
                      {fightError}
                    </div>
                  ) : (
                    <DataTable
                      columns={playerColumns}
                      data={fightPlayers}
                      rowKey={(r) => r.player_name}
                      emptyMessage="No player data"
                    />
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
