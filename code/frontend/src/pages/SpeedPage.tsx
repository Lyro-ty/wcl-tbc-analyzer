import { useCallback, useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { compareRaids, getReports, getReportSpeed, refreshSpeedRankings, type RankingsRefreshResponse } from '../lib/api'
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
  const [refreshing, setRefreshing] = useState(false)
  const [refreshResult, setRefreshResult] = useState<RankingsRefreshResponse | null>(null)

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

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    setRefreshResult(null)
    setError(null)
    try {
      const result = await refreshSpeedRankings()
      setRefreshResult(result)
      if (reportA && !reportB) loadSpeed()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to refresh speed rankings')
    } finally {
      setRefreshing(false)
    }
  }, [reportA, reportB, loadSpeed])

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

        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-700 disabled:opacity-50"
        >
          {refreshing ? (
            <><Loader2 className="h-4 w-4 animate-spin" /> Refreshing...</>
          ) : (
            <><RefreshCw className="h-4 w-4" /> Refresh Speed Rankings</>
          )}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {refreshResult && (
        <div className="mb-4 rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-4 text-sm text-emerald-400">
          Speed rankings refreshed: {refreshResult.fetched} fetched, {refreshResult.skipped} skipped
          {refreshResult.errors.length > 0 && (
            <span className="text-amber-400"> ({refreshResult.errors.length} errors)</span>
          )}
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

      {/* Empty state with CTA */}
      {!loading && !speedData && !compareData && reportA && (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-zinc-800 p-8 text-center">
          <p className="text-sm text-zinc-500">No speed data available. Click Load to fetch or refresh speed rankings first.</p>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 text-sm text-red-400 hover:text-red-300"
          >
            <RefreshCw className="h-4 w-4" /> Refresh speed rankings from WCL
          </button>
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
