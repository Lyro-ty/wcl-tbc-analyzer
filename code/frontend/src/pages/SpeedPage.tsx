import { useCallback, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { compareRaids, getReports, getReportSpeed } from '../lib/api'
import type { RaidComparison, SpeedComparison } from '../lib/types'
import { useApiQuery } from '../hooks/useApiQuery'
import SpeedComparisonChart from '../components/charts/SpeedComparisonChart'
import QuickAction from '../components/ui/QuickAction'
import { formatDuration, formatNumber } from '../lib/wow-classes'

export default function SpeedPage() {
  const { data: reports } = useApiQuery(() => getReports(), [])
  const [reportA, setReportA] = useState('')
  const [reportB, setReportB] = useState('')
  const [speedData, setSpeedData] = useState<SpeedComparison[] | null>(null)
  const [compareData, setCompareData] = useState<RaidComparison[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSpeed = useCallback(async () => {
    if (!reportA) return
    setLoading(true)
    setError(null)
    setCompareData(null)
    try {
      if (reportB) {
        const data = await compareRaids(reportA, reportB)
        setCompareData(data)
        setSpeedData(null)
      } else {
        const data = await getReportSpeed(reportA)
        setSpeedData(data)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [reportA, reportB])

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Raid Speed Comparison</h1>

      <div className="mb-6 flex flex-wrap gap-4">
        <select
          value={reportA}
          onChange={(e) => setReportA(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
        >
          <option value="">Select report...</option>
          {reports?.map((r) => (
            <option key={r.code} value={r.code}>{r.title} ({r.code})</option>
          ))}
        </select>

        <select
          value={reportB}
          onChange={(e) => setReportB(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
        >
          <option value="">Compare with... (optional)</option>
          {reports?.filter((r) => r.code !== reportA).map((r) => (
            <option key={r.code} value={r.code}>{r.title} ({r.code})</option>
          ))}
        </select>

        <button
          onClick={loadSpeed}
          disabled={!reportA || loading}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Load'}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Single report speed chart */}
      {speedData && speedData.length > 0 && (
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-zinc-200">Your Speed vs Top Rankings</h2>
            <QuickAction question={`Compare our speed in ${reportA} to top guilds`} />
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
            <SpeedComparisonChart data={speedData} />
          </div>
        </div>
      )}

      {/* Two-raid comparison */}
      {compareData && compareData.length > 0 && (
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-zinc-200">
              {reportA} vs {reportB}
            </h2>
            <QuickAction question={`Compare raids ${reportA} and ${reportB}`} />
          </div>
          <div className="space-y-3">
            {compareData.map((r) => {
              const timeDelta = (r.a_duration_ms && r.b_duration_ms)
                ? r.a_duration_ms - r.b_duration_ms : null
              const dpsDelta = (r.a_avg_dps && r.b_avg_dps)
                ? r.a_avg_dps - r.b_avg_dps : null
              const deathDelta = (r.a_deaths != null && r.b_deaths != null)
                ? r.a_deaths - r.b_deaths : null

              return (
                <div key={r.encounter_name} className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
                  <h3 className="mb-2 font-semibold text-zinc-100">{r.encounter_name}</h3>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-zinc-500">Time</span>
                      <div className="flex items-center gap-2">
                        <span>{r.a_duration_ms ? formatDuration(r.a_duration_ms) : '—'}</span>
                        <span className="text-zinc-600">vs</span>
                        <span>{r.b_duration_ms ? formatDuration(r.b_duration_ms) : '—'}</span>
                        {timeDelta !== null && (
                          <span className={timeDelta > 0 ? 'text-red-400' : 'text-emerald-400'}>
                            ({timeDelta > 0 ? '+' : ''}{Math.round(timeDelta / 1000)}s)
                          </span>
                        )}
                      </div>
                    </div>
                    <div>
                      <span className="text-zinc-500">Avg DPS</span>
                      <div className="flex items-center gap-2">
                        <span>{r.a_avg_dps ? formatNumber(r.a_avg_dps) : '—'}</span>
                        <span className="text-zinc-600">vs</span>
                        <span>{r.b_avg_dps ? formatNumber(r.b_avg_dps) : '—'}</span>
                        {dpsDelta !== null && (
                          <span className={dpsDelta > 0 ? 'text-emerald-400' : 'text-red-400'}>
                            ({dpsDelta > 0 ? '+' : ''}{formatNumber(dpsDelta)})
                          </span>
                        )}
                      </div>
                    </div>
                    <div>
                      <span className="text-zinc-500">Deaths</span>
                      <div className="flex items-center gap-2">
                        <span>{r.a_deaths ?? '—'}</span>
                        <span className="text-zinc-600">vs</span>
                        <span>{r.b_deaths ?? '—'}</span>
                        {deathDelta !== null && (
                          <span className={deathDelta > 0 ? 'text-red-400' : 'text-emerald-400'}>
                            ({deathDelta > 0 ? '+' : ''}{deathDelta})
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
