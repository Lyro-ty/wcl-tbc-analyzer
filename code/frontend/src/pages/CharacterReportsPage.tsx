import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Skull, Swords, Target, UserCheck } from 'lucide-react'
import { getCharacterReports, getCharacters } from '../lib/api'
import type { CharacterReportSummary } from '../lib/types'
import { useApiQuery } from '../hooks/useApiQuery'
import { classColor, formatDate, formatNumber } from '../lib/wow-classes'
import IngestForm from '../components/ui/IngestForm'

function parseColor(parse: number | null): string {
  if (parse == null) return 'text-zinc-500'
  if (parse >= 99) return 'text-orange-300'
  if (parse >= 95) return 'text-orange-400'
  if (parse >= 75) return 'text-purple-400'
  if (parse >= 50) return 'text-blue-400'
  if (parse >= 25) return 'text-green-400'
  return 'text-zinc-400'
}

export default function CharacterReportsPage() {
  const { data: characters, loading: loadingChars } = useApiQuery(() => getCharacters(), [])
  const [selectedChar, setSelectedChar] = useState<string>('')
  const [reports, setReports] = useState<CharacterReportSummary[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchReports = useCallback(async (name: string) => {
    if (!name) {
      setReports(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await getCharacterReports(name)
      setReports(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch reports')
      setReports(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleCharacterChange = useCallback((name: string) => {
    setSelectedChar(name)
    fetchReports(name)
  }, [fetchReports])

  const selectedInfo = characters?.find((c) => c.name === selectedChar)

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Character Reports</h1>

      <div className="mb-6">
        <IngestForm onIngested={() => { if (selectedChar) fetchReports(selectedChar) }} />
      </div>

      {/* Character selector */}
      <div className="mb-6">
        <label className="mb-1 block text-xs font-medium text-zinc-400">
          Select a character
        </label>
        <select
          value={selectedChar}
          onChange={(e) => handleCharacterChange(e.target.value)}
          disabled={loadingChars}
          className="w-full max-w-xs rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100 focus:border-zinc-500 focus:outline-none disabled:opacity-50"
        >
          <option value="">— Choose character —</option>
          {characters?.map((c) => (
            <option key={c.id} value={c.name}>
              {c.name} ({c.spec} {c.character_class} — {c.server_slug})
            </option>
          ))}
        </select>
        {selectedInfo && (
          <p className="mt-1.5 text-xs text-zinc-500">
            <span style={{ color: classColor(selectedInfo.character_class) }}>
              {selectedInfo.spec} {selectedInfo.character_class}
            </span>
            {' '}&middot; {selectedInfo.server_slug}-{selectedInfo.server_region}
          </p>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-lg bg-zinc-800/50" />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-6 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Empty — no character selected */}
      {!selectedChar && !loading && (
        <div className="flex flex-col items-center gap-4 py-20 text-zinc-500">
          <UserCheck className="h-12 w-12" />
          <p className="text-lg font-medium">Select a character to view their reports</p>
          <p className="text-sm">Choose from your registered characters above.</p>
        </div>
      )}

      {/* Empty — character selected but no reports */}
      {selectedChar && !loading && !error && reports && reports.length === 0 && (
        <div className="flex flex-col items-center gap-4 py-20 text-zinc-500">
          <FileText className="h-12 w-12" />
          <p className="text-lg font-medium">No reports found for {selectedChar}</p>
          <p className="text-sm">Ingest a report containing this character's data first.</p>
        </div>
      )}

      {/* Report list */}
      {!loading && reports && reports.length > 0 && (
        <div className="space-y-2">
          {reports.map((r) => (
            <Link
              key={r.code}
              to={`/character-reports/${encodeURIComponent(selectedChar)}/${r.code}`}
              className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/50 px-5 py-4 transition-colors hover:border-zinc-700 hover:bg-zinc-900"
            >
              <div>
                <p className="font-semibold text-zinc-100">{r.title}</p>
                <p className="mt-0.5 text-sm text-zinc-400">
                  {formatDate(r.start_time)} &middot; {r.guild_name ?? 'Unknown Guild'} &middot;{' '}
                  {r.code}
                </p>
              </div>
              <div className="flex items-center gap-6 text-sm">
                <div className="text-right">
                  <div className="flex items-center gap-1.5 text-zinc-400">
                    <Swords className="h-3.5 w-3.5" />
                    <span>{r.fight_count} fights</span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-emerald-500">
                    <Target className="h-3.5 w-3.5" />
                    <span>{r.kill_count} kills</span>
                  </div>
                </div>
                <div className="text-right">
                  {r.avg_dps != null && (
                    <p className="text-zinc-300">{formatNumber(r.avg_dps)} DPS</p>
                  )}
                  {r.avg_parse != null && (
                    <p className={`mt-0.5 ${parseColor(r.avg_parse)}`}>
                      {r.avg_parse}% avg parse
                    </p>
                  )}
                </div>
                <div className="text-right">
                  {r.total_deaths != null && r.total_deaths > 0 && (
                    <p className="flex items-center gap-1 text-red-400">
                      <Skull className="h-3.5 w-3.5" />
                      {r.total_deaths}
                    </p>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
