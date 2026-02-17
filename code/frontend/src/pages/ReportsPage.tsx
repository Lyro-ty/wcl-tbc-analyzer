import { Link } from 'react-router-dom'
import { FileText } from 'lucide-react'
import { getReports } from '../lib/api'
import { formatDate } from '../lib/wow-classes'
import { useApiQuery } from '../hooks/useApiQuery'
import IngestForm from '../components/ui/IngestForm'

export default function ReportsPage() {
  const { data: reports, loading, error, refetch } = useApiQuery(() => getReports(), [])

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Raid Reports</h1>

      {/* Ingest form */}
      <div className="mb-6">
        <IngestForm onIngested={refetch} />
      </div>

      {/* Loading state */}
      {loading && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-zinc-800/50" />
          ))}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-6 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && !reports?.length && (
        <div className="flex flex-col items-center gap-4 py-20 text-zinc-500">
          <FileText className="h-12 w-12" />
          <p className="text-lg font-medium">No reports ingested yet</p>
          <p className="text-sm">Paste a WCL report code above to pull your first report.</p>
        </div>
      )}

      {/* Report list */}
      {!loading && reports && reports.length > 0 && (
        <div className="space-y-2">
          {reports.map((r) => (
            <Link
              key={r.code}
              to={`/reports/${r.code}`}
              className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/50 px-5 py-4 transition-colors hover:border-zinc-700 hover:bg-zinc-900"
            >
              <div>
                <p className="font-semibold text-zinc-100">{r.title}</p>
                <p className="mt-0.5 text-sm text-zinc-400">
                  {formatDate(r.start_time)} &middot; {r.guild_name ?? 'Unknown Guild'} &middot;{' '}
                  {r.code}
                </p>
              </div>
              <div className="text-right text-sm text-zinc-400">
                <p>{r.fight_count} fights</p>
                <p>{r.boss_count} bosses</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
