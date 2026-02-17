import { useCallback, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getEncounters, getLeaderboard } from '../lib/api'
import type { SpecLeaderboardEntry } from '../lib/types'
import { useApiQuery } from '../hooks/useApiQuery'
import DataTable, { type Column } from '../components/ui/DataTable'
import DpsBarChart from '../components/charts/DpsBarChart'
import QuickAction from '../components/ui/QuickAction'
import { classColor, formatNumber } from '../lib/wow-classes'

export default function LeaderboardPage() {
  const { data: encounters } = useApiQuery(() => getEncounters(), [])
  const [selectedEnc, setSelectedEnc] = useState('')
  const [leaderboard, setLeaderboard] = useState<SpecLeaderboardEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!selectedEnc) return
    setLoading(true)
    setError(null)
    try {
      const data = await getLeaderboard(selectedEnc)
      setLeaderboard(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [selectedEnc])

  const columns: Column<SpecLeaderboardEntry>[] = [
    { key: 'rank', label: '#', render: (_r, i) => (
      <span className="font-mono text-zinc-500">{i + 1}</span>
    )},
    { key: 'spec', label: 'Spec', render: (r) => (
      <span style={{ color: classColor(r.player_class) }}>
        {r.player_spec} {r.player_class}
      </span>
    )},
    { key: 'avg_dps', label: 'Avg DPS', sortValue: (r) => r.avg_dps, render: (r) => formatNumber(r.avg_dps) },
    { key: 'max_dps', label: 'Max DPS', sortValue: (r) => r.max_dps, render: (r) => formatNumber(r.max_dps) },
    { key: 'median_dps', label: 'Median DPS', sortValue: (r) => r.median_dps, render: (r) => formatNumber(r.median_dps) },
    { key: 'avg_parse', label: 'Avg Parse', sortValue: (r) => r.avg_parse ?? 0, render: (r) => (
      r.avg_parse != null ? `${r.avg_parse}%` : '—'
    )},
    { key: 'avg_ilvl', label: 'Avg iLvl', sortValue: (r) => r.avg_ilvl ?? 0, render: (r) => (
      r.avg_ilvl != null ? r.avg_ilvl.toFixed(1) : '—'
    )},
    { key: 'sample', label: 'Samples', sortValue: (r) => r.sample_size, render: (r) => r.sample_size },
  ]

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Spec Leaderboard</h1>

      <div className="mb-6 flex flex-wrap gap-4">
        <select
          value={selectedEnc}
          onChange={(e) => setSelectedEnc(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
        >
          <option value="">Select encounter...</option>
          {encounters?.map((e) => (
            <option key={e.id} value={e.name}>{e.name} ({e.zone_name})</option>
          ))}
        </select>

        <button
          onClick={load}
          disabled={!selectedEnc || loading}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Load'}
        </button>

        {selectedEnc && (
          <QuickAction question={`What spec should I play on ${selectedEnc}?`} />
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {leaderboard && leaderboard.length > 0 && (
        <>
          <div className="mb-6 rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
            <DpsBarChart data={leaderboard} />
          </div>
          <DataTable
            columns={columns}
            data={leaderboard}
            rowKey={(r) => `${r.player_spec}-${r.player_class}`}
          />
        </>
      )}

      {leaderboard?.length === 0 && (
        <div className="rounded-lg border border-zinc-800 p-8 text-center text-sm text-zinc-500">
          No leaderboard data for this encounter.
        </div>
      )}
    </div>
  )
}
