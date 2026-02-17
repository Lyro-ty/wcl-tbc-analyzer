import { useParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Shield, Skull, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getCharacterReportDetail } from '../lib/api'
import { useApiQuery } from '../hooks/useApiQuery'
import { classColor, formatDuration, formatNumber } from '../lib/wow-classes'
import QuickAction from '../components/ui/QuickAction'

function parseColor(parse: number | null): string {
  if (parse == null) return 'text-zinc-500'
  if (parse >= 99) return 'text-orange-300'
  if (parse >= 95) return 'text-orange-400'
  if (parse >= 75) return 'text-purple-400'
  if (parse >= 50) return 'text-blue-400'
  if (parse >= 25) return 'text-green-400'
  return 'text-zinc-400'
}

function parseBorder(parse: number | null): string {
  if (parse == null) return 'border-zinc-800'
  if (parse >= 95) return 'border-orange-900/50'
  if (parse >= 75) return 'border-purple-900/50'
  if (parse >= 50) return 'border-blue-900/50'
  return 'border-zinc-800'
}

export default function CharacterReportDetailPage() {
  const { name, code } = useParams<{ name: string; code: string }>()

  const { data: fights, loading, error } = useApiQuery(
    () => getCharacterReportDetail(name!, code!), [name, code],
  )

  // Summary stats
  const avgDps = fights && fights.length > 0
    ? fights.reduce((sum, f) => sum + f.dps, 0) / fights.length
    : null
  const bestParse = fights && fights.length > 0
    ? Math.max(...fights.map((f) => f.parse_percentile ?? 0))
    : null
  const totalDeaths = fights
    ? fights.reduce((sum, f) => sum + f.deaths, 0)
    : null
  const kills = fights ? fights.filter((f) => f.kill).length : 0
  const wipes = fights ? fights.filter((f) => !f.kill).length : 0

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-36 animate-pulse rounded-lg bg-zinc-800/50" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <div className="mb-6 flex items-center gap-3">
          <Link to="/character-reports" className="text-zinc-400 hover:text-zinc-200">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold">{name} — {code}</h1>
        </div>
        <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-6 text-sm text-red-400">
          {error}
        </div>
      </div>
    )
  }

  const playerClass = fights?.[0]?.player_class ?? ''
  const playerSpec = fights?.[0]?.player_spec ?? ''

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <Link to="/character-reports" className="text-zinc-400 hover:text-zinc-200">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">
            <span style={{ color: classColor(playerClass) }}>{name}</span>
            <span className="text-zinc-500"> in </span>
            {code}
          </h1>
          {playerSpec && (
            <p className="text-sm text-zinc-400">
              {playerSpec} {playerClass}
            </p>
          )}
        </div>
        <div className="ml-auto">
          <QuickAction question={`Analyze ${name}'s performance in report ${code}`} />
        </div>
      </div>

      {/* Summary bar */}
      {fights && fights.length > 0 && (
        <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Avg DPS</p>
            <p className="mt-1 text-lg font-bold text-zinc-100">
              {avgDps != null ? formatNumber(avgDps) : '—'}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Best Parse</p>
            <p className={`mt-1 text-lg font-bold ${parseColor(bestParse)}`}>
              {bestParse != null ? `${bestParse}%` : '—'}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Kills</p>
            <p className="mt-1 text-lg font-bold text-emerald-500">{kills}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Wipes</p>
            <p className={`mt-1 text-lg font-bold ${wipes > 0 ? 'text-red-400' : 'text-zinc-300'}`}>
              {wipes}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Total Deaths</p>
            <p className={`mt-1 text-lg font-bold ${(totalDeaths ?? 0) > 0 ? 'text-red-400' : 'text-zinc-300'}`}>
              {totalDeaths ?? 0}
            </p>
          </div>
        </div>
      )}

      {/* Per-boss cards */}
      <h2 className="mb-4 text-lg font-semibold text-zinc-200">Boss Performances</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {fights?.map((fight) => (
          <div
            key={fight.fight_id}
            className={`rounded-lg border bg-zinc-900/50 p-4 ${
              fight.kill ? parseBorder(fight.parse_percentile) : 'border-red-900/50'
            }`}
          >
            {/* Boss header */}
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-semibold text-zinc-100">
                {fight.encounter_name ?? 'Unknown Boss'}
              </h3>
              {fight.kill ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-500" />
              ) : (
                <Skull className="h-5 w-5 text-red-500" />
              )}
            </div>

            {/* Class/spec accent */}
            <div
              className="mb-3 inline-block rounded px-2 py-0.5 text-xs font-medium"
              style={{
                backgroundColor: classColor(fight.player_class) + '18',
                color: classColor(fight.player_class),
              }}
            >
              {fight.player_spec} {fight.player_class}
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-zinc-500">DPS</span>
                <p className="font-mono text-zinc-300">{formatNumber(fight.dps)}</p>
              </div>
              <div>
                <span className="text-zinc-500">Parse</span>
                <p className={`font-mono ${parseColor(fight.parse_percentile)}`}>
                  {fight.parse_percentile != null ? `${fight.parse_percentile}%` : '—'}
                </p>
              </div>
              <div>
                <span className="text-zinc-500">Time</span>
                <p className="font-mono text-zinc-300">{formatDuration(fight.duration_ms)}</p>
              </div>
              <div>
                <span className="text-zinc-500">Deaths</span>
                <p className={`font-mono ${fight.deaths > 0 ? 'text-red-400' : 'text-zinc-300'}`}>
                  {fight.deaths}
                </p>
              </div>
            </div>

            {/* Utility row */}
            {(fight.interrupts > 0 || fight.dispels > 0 || fight.item_level != null) && (
              <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-zinc-800 pt-3 text-xs text-zinc-500">
                {fight.interrupts > 0 && (
                  <span className="flex items-center gap-1">
                    <Zap className="h-3 w-3" /> {fight.interrupts} int
                  </span>
                )}
                {fight.dispels > 0 && (
                  <span className="flex items-center gap-1">
                    <Shield className="h-3 w-3" /> {fight.dispels} disp
                  </span>
                )}
                {fight.item_level != null && (
                  <span className="ml-auto">iLvl {fight.item_level.toFixed(0)}</span>
                )}
              </div>
            )}

            {/* Kill/wipe footer */}
            <div className="mt-2 flex items-center justify-between">
              <span className="text-xs text-zinc-500">
                {fight.kill ? 'Kill' : 'Wipe'} &middot; {formatDuration(fight.duration_ms)}
              </span>
              <QuickAction
                question={`How did ${name} do on ${fight.encounter_name} in ${code}?`}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
