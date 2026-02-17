import { useCallback, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { compareRaids, getReports } from '../lib/api'
import type { RaidComparison } from '../lib/types'
import { useApiQuery } from '../hooks/useApiQuery'
import QuickAction from '../components/ui/QuickAction'
import { formatDuration, formatNumber } from '../lib/wow-classes'

export default function ComparePage() {
  const { data: reports } = useApiQuery(() => getReports(), [])
  const [reportA, setReportA] = useState('')
  const [reportB, setReportB] = useState('')
  const [comparison, setComparison] = useState<RaidComparison[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!reportA || !reportB) return
    setLoading(true)
    setError(null)
    try {
      setComparison(await compareRaids(reportA, reportB))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [reportA, reportB])

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Compare Two Raids</h1>

      <div className="mb-6 flex flex-wrap gap-4">
        <select
          value={reportA}
          onChange={(e) => setReportA(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
        >
          <option value="">Raid A...</option>
          {reports?.map((r) => (
            <option key={r.code} value={r.code}>{r.title} ({r.code})</option>
          ))}
        </select>

        <select
          value={reportB}
          onChange={(e) => setReportB(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
        >
          <option value="">Raid B...</option>
          {reports?.filter((r) => r.code !== reportA).map((r) => (
            <option key={r.code} value={r.code}>{r.title} ({r.code})</option>
          ))}
        </select>

        <button
          onClick={load}
          disabled={!reportA || !reportB || loading}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Compare'}
        </button>

        {reportA && reportB && (
          <QuickAction question={`Compare raids ${reportA} and ${reportB}`} />
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {comparison && comparison.length > 0 && (
        <div className="space-y-3">
          {comparison.map((r) => {
            const timeDelta = (r.a_duration_ms && r.b_duration_ms)
              ? r.a_duration_ms - r.b_duration_ms : null
            const dpsDelta = (r.a_avg_dps && r.b_avg_dps)
              ? r.a_avg_dps - r.b_avg_dps : null
            const deathDelta = (r.a_deaths != null && r.b_deaths != null)
              ? r.a_deaths - r.b_deaths : null

            return (
              <div key={r.encounter_name} className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
                <h3 className="mb-3 font-semibold text-zinc-100">{r.encounter_name}</h3>
                <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-4">
                  <div>
                    <span className="text-xs text-zinc-500">Time A</span>
                    <p>{r.a_duration_ms ? formatDuration(r.a_duration_ms) : '—'}</p>
                  </div>
                  <div>
                    <span className="text-xs text-zinc-500">Time B</span>
                    <p>{r.b_duration_ms ? formatDuration(r.b_duration_ms) : '—'}</p>
                  </div>
                  <div>
                    <span className="text-xs text-zinc-500">DPS A</span>
                    <p>{r.a_avg_dps ? formatNumber(r.a_avg_dps) : '—'}</p>
                  </div>
                  <div>
                    <span className="text-xs text-zinc-500">DPS B</span>
                    <p>{r.b_avg_dps ? formatNumber(r.b_avg_dps) : '—'}</p>
                  </div>
                  {timeDelta !== null && (
                    <div className="col-span-2">
                      <span className="text-xs text-zinc-500">Time delta</span>
                      <p className={timeDelta > 0 ? 'text-red-400' : 'text-emerald-400'}>
                        {timeDelta > 0 ? 'B' : 'A'} faster by {Math.abs(Math.round(timeDelta / 1000))}s
                      </p>
                    </div>
                  )}
                  {dpsDelta !== null && (
                    <div>
                      <span className="text-xs text-zinc-500">DPS delta</span>
                      <p className={dpsDelta > 0 ? 'text-emerald-400' : 'text-red-400'}>
                        {dpsDelta > 0 ? '+' : ''}{formatNumber(dpsDelta)}
                      </p>
                    </div>
                  )}
                  {deathDelta !== null && (
                    <div>
                      <span className="text-xs text-zinc-500">Death delta</span>
                      <p className={deathDelta > 0 ? 'text-red-400' : 'text-emerald-400'}>
                        {deathDelta > 0 ? '+' : ''}{deathDelta}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {comparison?.length === 0 && (
        <div className="rounded-lg border border-zinc-800 p-8 text-center text-sm text-zinc-500">
          No shared boss kills found between these two reports.
        </div>
      )}
    </div>
  )
}
