import { useCallback, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getFightDetails, getReports, getReportSummary } from '../lib/api'
import type { FightPlayer, RaidSummaryFight } from '../lib/types'
import { useApiQuery } from '../hooks/useApiQuery'
import DataTable, { type Column } from '../components/ui/DataTable'
import QuickAction from '../components/ui/QuickAction'
import { classColor, formatNumber, parseColor } from '../lib/wow-classes'

export default function RosterPage() {
  const { data: reports } = useApiQuery(() => getReports(), [])
  const [selectedReport, setSelectedReport] = useState('')
  const [fights, setFights] = useState<RaidSummaryFight[]>([])
  const [selectedFight, setSelectedFight] = useState<number | null>(null)
  const [players, setPlayers] = useState<FightPlayer[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadReport = useCallback(async (code: string) => {
    setSelectedReport(code)
    setSelectedFight(null)
    setPlayers([])
    setError(null)
    if (!code) return
    try {
      const data = await getReportSummary(code)
      setFights(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load report')
      setFights([])
    }
  }, [])

  const loadFight = useCallback(async (fightId: number) => {
    setSelectedFight(fightId)
    setLoading(true)
    setError(null)
    try {
      const data = await getFightDetails(selectedReport, fightId)
      setPlayers(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
      setPlayers([])
    } finally {
      setLoading(false)
    }
  }, [selectedReport])

  // Find highlight values
  const maxDeaths = Math.max(...players.map((p) => p.deaths), 0)
  const maxInterrupts = Math.max(...players.map((p) => p.interrupts), 0)
  const maxDps = Math.max(...players.map((p) => p.dps), 0)
  const encounterName = players[0]?.encounter_name ?? ''

  const columns: Column<FightPlayer>[] = [
    { key: 'name', label: 'Player', render: (r) => (
      selectedReport && selectedFight ? (
        <Link
          to={`/reports/${selectedReport}/fights/${selectedFight}/player/${encodeURIComponent(r.player_name)}`}
          className="font-medium underline decoration-zinc-700 underline-offset-2 hover:decoration-zinc-400"
          style={{ color: classColor(r.player_class) }}
        >
          {r.player_name}
        </Link>
      ) : (
        <span className="font-medium" style={{ color: classColor(r.player_class) }}>
          {r.player_name}
        </span>
      )
    )},
    { key: 'spec', label: 'Spec', render: (r) => (
      <span className="text-zinc-400">{r.player_spec} {r.player_class}</span>
    )},
    { key: 'dps', label: 'DPS', sortValue: (r) => r.dps, render: (r) => (
      <span className={r.dps === maxDps && maxDps > 0 ? 'font-bold text-amber-400' : ''}>
        {formatNumber(r.dps)}
      </span>
    )},
    { key: 'parse', label: 'Parse', sortValue: (r) => r.parse_percentile ?? 0, render: (r) => (
      <span className={parseColor(r.parse_percentile)}>
        {r.parse_percentile != null ? `${r.parse_percentile}%` : '—'}
      </span>
    )},
    { key: 'deaths', label: 'Deaths', sortValue: (r) => r.deaths, render: (r) => (
      <span className={r.deaths === maxDeaths && maxDeaths > 0 ? 'font-bold text-red-400' : r.deaths > 0 ? 'text-red-400' : ''}>
        {r.deaths}
      </span>
    )},
    { key: 'interrupts', label: 'Interrupts', sortValue: (r) => r.interrupts, render: (r) => (
      <span className={r.interrupts === maxInterrupts && maxInterrupts > 0 ? 'font-bold text-emerald-400' : ''}>
        {r.interrupts}
      </span>
    )},
    { key: 'dispels', label: 'Dispels', sortValue: (r) => r.dispels, render: (r) => r.dispels },
    { key: 'ilvl', label: 'iLvl', sortValue: (r) => r.item_level ?? 0, render: (r) => (
      r.item_level != null ? r.item_level.toFixed(1) : '—'
    )},
  ]

  // Accountability: death totals across all bosses
  const [accountability, setAccountability] = useState<Map<string, { deaths: number, className: string }>>(new Map())

  const [accountabilityWarning, setAccountabilityWarning] = useState<string | null>(null)

  const loadAccountability = useCallback(async () => {
    if (!selectedReport || fights.length === 0) return
    setLoading(true)
    setAccountabilityWarning(null)
    const totals = new Map<string, { deaths: number, className: string }>()
    let failedCount = 0
    for (const fight of fights) {
      try {
        const data = await getFightDetails(selectedReport, fight.fight_id)
        for (const p of data) {
          const existing = totals.get(p.player_name)
          if (existing) {
            existing.deaths += p.deaths
          } else {
            totals.set(p.player_name, { deaths: p.deaths, className: p.player_class })
          }
        }
      } catch {
        failedCount++
      }
    }
    if (failedCount > 0) {
      setAccountabilityWarning(
        `Failed to load ${failedCount} of ${fights.length} fights — totals may be incomplete.`,
      )
    }
    setAccountability(totals)
    setLoading(false)
  }, [selectedReport, fights])

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Raid Roster</h1>

      <div className="mb-6 flex flex-wrap gap-4">
        <select
          value={selectedReport}
          onChange={(e) => loadReport(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
        >
          <option value="">Select report...</option>
          {reports?.map((r) => (
            <option key={r.code} value={r.code}>{r.title} ({r.code})</option>
          ))}
        </select>

        {fights.length > 0 && (
          <select
            value={selectedFight ?? ''}
            onChange={(e) => e.target.value && loadFight(Number(e.target.value))}
            className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
          >
            <option value="">Select boss...</option>
            {fights.map((f) => (
              <option key={f.fight_id} value={f.fight_id}>
                {f.encounter_name} ({f.kill ? 'Kill' : 'Wipe'})
              </option>
            ))}
          </select>
        )}

        {fights.length > 0 && (
          <button
            onClick={loadAccountability}
            disabled={loading}
            className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-700 disabled:opacity-50"
          >
            Death Accountability
          </button>
        )}

        {encounterName && (
          <QuickAction question={`Analyze deaths on ${encounterName} in ${selectedReport}`} />
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 py-8 text-sm text-zinc-400">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading...
        </div>
      )}

      {!loading && players.length > 0 && (
        <DataTable
          columns={columns}
          data={players}
          rowKey={(r) => r.player_name}
        />
      )}

      {/* Death accountability table */}
      {accountability.size > 0 && (
        <div className="mt-8">
          <h2 className="mb-4 text-lg font-semibold text-zinc-200">Death Accountability (Full Raid)</h2>
          {accountabilityWarning && (
            <div className="mb-3 rounded-lg border border-amber-900/50 bg-amber-950/20 p-3 text-sm text-amber-400">
              {accountabilityWarning}
            </div>
          )}
          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/50">
                  <th className="px-4 py-3 text-left font-medium text-zinc-400">Player</th>
                  <th className="px-4 py-3 text-left font-medium text-zinc-400">Total Deaths</th>
                </tr>
              </thead>
              <tbody>
                {[...accountability.entries()]
                  .sort(([, a], [, b]) => b.deaths - a.deaths)
                  .map(([name, { deaths, className }]) => (
                    <tr key={name} className="border-b border-zinc-800/50">
                      <td className="px-4 py-2.5" style={{ color: classColor(className) }}>{name}</td>
                      <td className={`px-4 py-2.5 font-mono ${deaths > 3 ? 'text-red-400 font-bold' : ''}`}>
                        {deaths}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
