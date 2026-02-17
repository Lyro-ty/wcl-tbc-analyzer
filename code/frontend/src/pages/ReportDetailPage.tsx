import { useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getFightDetails, getReportExecution, getReportSpeed, getReportSummary } from '../lib/api'
import type { FightPlayer } from '../lib/types'
import { useApiQuery } from '../hooks/useApiQuery'
import BossCard from '../components/ui/BossCard'
import DataTable, { type Column } from '../components/ui/DataTable'
import QuickAction from '../components/ui/QuickAction'
import SpeedComparisonChart from '../components/charts/SpeedComparisonChart'
import { classColor, formatDuration, formatNumber } from '../lib/wow-classes'

export default function ReportDetailPage() {
  const { code } = useParams<{ code: string }>()
  const [expandedFight, setExpandedFight] = useState<number | null>(null)
  const [fightPlayers, setFightPlayers] = useState<FightPlayer[]>([])
  const [loadingFight, setLoadingFight] = useState(false)

  const { data: summary, loading: loadSummary } = useApiQuery(
    () => getReportSummary(code!), [code],
  )
  const { data: execution } = useApiQuery(
    () => getReportExecution(code!), [code],
  )
  const { data: speed } = useApiQuery(
    () => getReportSpeed(code!), [code],
  )

  const toggleFight = useCallback(async (fightId: number) => {
    if (expandedFight === fightId) {
      setExpandedFight(null)
      return
    }
    setExpandedFight(fightId)
    setLoadingFight(true)
    try {
      const players = await getFightDetails(code!, fightId)
      setFightPlayers(players)
    } catch {
      setFightPlayers([])
    } finally {
      setLoadingFight(false)
    }
  }, [code, expandedFight])

  const playerColumns: Column<FightPlayer>[] = [
    { key: 'name', label: 'Player', render: (r) => (
      <span style={{ color: classColor(r.player_class) }}>{r.player_name}</span>
    )},
    { key: 'spec', label: 'Spec', render: (r) => (
      <span className="text-zinc-400">{r.player_spec} {r.player_class}</span>
    )},
    { key: 'dps', label: 'DPS', sortValue: (r) => r.dps, render: (r) => formatNumber(r.dps) },
    { key: 'parse', label: 'Parse', sortValue: (r) => r.parse_percentile ?? 0, render: (r) => (
      <span className={
        (r.parse_percentile ?? 0) >= 95 ? 'text-orange-400' :
        (r.parse_percentile ?? 0) >= 75 ? 'text-purple-400' :
        (r.parse_percentile ?? 0) >= 50 ? 'text-blue-400' : 'text-zinc-400'
      }>{r.parse_percentile != null ? `${r.parse_percentile}%` : '—'}</span>
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
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
            <SpeedComparisonChart data={speed} />
          </div>
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
