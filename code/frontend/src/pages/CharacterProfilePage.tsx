import { useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  getCharacterProfile,
  getCharacterRecentParses,
  getEncounters,
  getProgression,
} from '../lib/api'
import type { CharacterRecentParse, ProgressionPoint } from '../lib/types'
import { useApiQuery } from '../hooks/useApiQuery'
import DataTable, { type Column } from '../components/ui/DataTable'
import ProgressionLineChart from '../components/charts/ProgressionLineChart'
import QuickAction from '../components/ui/QuickAction'
import { classColor, formatDuration, formatNumber, parseColor } from '../lib/wow-classes'

export default function CharacterProfilePage() {
  const { name } = useParams<{ name: string }>()

  const { data: profile, loading: loadingProfile, error: profileError } = useApiQuery(
    () => getCharacterProfile(name!), [name],
  )
  const { data: parses, loading: loadingParses } = useApiQuery(
    () => getCharacterRecentParses(name!), [name],
  )
  const { data: encounters } = useApiQuery(() => getEncounters(), [])

  // Progression section
  const [selectedEnc, setSelectedEnc] = useState('')
  const [progression, setProgression] = useState<ProgressionPoint[] | null>(null)
  const [loadingProg, setLoadingProg] = useState(false)

  const loadProgression = useCallback(async (encounter: string) => {
    setSelectedEnc(encounter)
    if (!encounter) {
      setProgression(null)
      return
    }
    setLoadingProg(true)
    try {
      const data = await getProgression(name!, encounter)
      setProgression(data)
    } catch {
      setProgression(null)
    } finally {
      setLoadingProg(false)
    }
  }, [name])

  const parseColumns: Column<CharacterRecentParse>[] = [
    {
      key: 'encounter',
      label: 'Encounter',
      render: (r) => (
        <Link
          to={`/reports/${r.report_code}/fights/${r.fight_id}/player/${encodeURIComponent(name!)}`}
          className="font-medium text-zinc-200 underline decoration-zinc-700 underline-offset-2 hover:decoration-zinc-400"
        >
          {r.encounter_name}
        </Link>
      ),
    },
    {
      key: 'dps',
      label: 'DPS',
      sortValue: (r) => r.dps,
      render: (r) => <span className="font-mono">{formatNumber(r.dps)}</span>,
    },
    {
      key: 'parse',
      label: 'Parse',
      sortValue: (r) => r.parse_percentile ?? 0,
      render: (r) => (
        <span className={`font-mono ${parseColor(r.parse_percentile)}`}>
          {r.parse_percentile != null ? `${r.parse_percentile}%` : '—'}
        </span>
      ),
    },
    {
      key: 'deaths',
      label: 'Deaths',
      sortValue: (r) => r.deaths,
      render: (r) => (
        <span className={r.deaths > 0 ? 'text-red-400' : ''}>{r.deaths}</span>
      ),
    },
    {
      key: 'duration',
      label: 'Duration',
      sortValue: (r) => r.duration_ms,
      render: (r) => formatDuration(r.duration_ms),
    },
    {
      key: 'result',
      label: 'Result',
      render: (r) => (
        <span className={r.kill ? 'text-emerald-500' : 'text-red-400'}>
          {r.kill ? 'Kill' : 'Wipe'}
        </span>
      ),
    },
    {
      key: 'report',
      label: 'Report',
      render: (r) => (
        <Link
          to={`/reports/${r.report_code}`}
          className="font-mono text-xs text-zinc-500 hover:text-zinc-300"
        >
          {r.report_code.slice(0, 8)}
        </Link>
      ),
    },
  ]

  if (loadingProfile) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
      </div>
    )
  }

  if (profileError) {
    return (
      <div>
        <div className="mb-6 flex items-center gap-3">
          <Link to="/characters" className="text-zinc-400 hover:text-zinc-200">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold">{name}</h1>
        </div>
        <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-6 text-sm text-red-400">
          {profileError}
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <Link to="/characters" className="text-zinc-400 hover:text-zinc-200">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">
            <span style={{ color: classColor(profile?.character_class ?? '') }}>
              {name}
            </span>
          </h1>
          {profile && (
            <p className="text-sm text-zinc-400">
              {profile.spec} {profile.character_class}
              <span className="mx-2 text-zinc-600">|</span>
              {profile.server_slug}-{profile.server_region}
            </p>
          )}
        </div>
        <QuickAction
          question={`How can I improve as ${profile?.spec ?? ''} ${profile?.character_class ?? ''}?`}
        />
      </div>

      {/* Stats bar */}
      {profile && (
        <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Total Fights</p>
            <p className="mt-1 text-lg font-bold text-zinc-100">{profile.total_fights}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Total Kills</p>
            <p className="mt-1 text-lg font-bold text-emerald-500">{profile.total_kills}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Avg DPS</p>
            <p className="mt-1 text-lg font-bold text-zinc-100">
              {profile.avg_dps != null ? formatNumber(profile.avg_dps) : '—'}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Best Parse</p>
            <p className={`mt-1 text-lg font-bold ${parseColor(profile.best_parse)}`}>
              {profile.best_parse != null ? `${profile.best_parse}%` : '—'}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Total Deaths</p>
            <p className={`mt-1 text-lg font-bold ${profile.total_deaths > 0 ? 'text-red-400' : 'text-zinc-300'}`}>
              {profile.total_deaths}
            </p>
          </div>
        </div>
      )}

      {/* Recent parses */}
      <h2 className="mb-4 text-lg font-semibold text-zinc-200">Recent Parses</h2>
      {loadingParses ? (
        <div className="flex items-center gap-2 py-8 text-sm text-zinc-400">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading parses...
        </div>
      ) : parses && parses.length > 0 ? (
        <div className="mb-8">
          <DataTable
            columns={parseColumns}
            data={parses}
            rowKey={(r) => `${r.report_code}-${r.fight_id}`}
          />
        </div>
      ) : (
        <div className="mb-8 rounded-lg border border-zinc-800 p-6 text-center text-sm text-zinc-500">
          No recent parses found. Ingest a report containing this character.
        </div>
      )}

      {/* Progression */}
      <h2 className="mb-4 text-lg font-semibold text-zinc-200">Progression</h2>
      <div className="mb-4">
        <select
          value={selectedEnc}
          onChange={(e) => loadProgression(e.target.value)}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
        >
          <option value="">Select encounter...</option>
          {encounters?.map((e) => (
            <option key={e.id} value={e.name}>{e.name}</option>
          ))}
        </select>
      </div>

      {loadingProg && (
        <div className="flex items-center gap-2 py-8 text-sm text-zinc-400">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading progression...
        </div>
      )}

      {progression && progression.length > 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
          <ProgressionLineChart data={progression} />
        </div>
      )}

      {selectedEnc && !loadingProg && progression && progression.length === 0 && (
        <div className="rounded-lg border border-zinc-800 p-6 text-center text-sm text-zinc-500">
          No progression data for {selectedEnc}. Run a progression snapshot first.
        </div>
      )}
    </div>
  )
}
