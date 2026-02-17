import { CheckCircle2, FileText, MessageSquare, Skull, Swords, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getDashboardRecent, getDashboardStats } from '../lib/api'
import { useApiQuery } from '../hooks/useApiQuery'
import IngestForm from '../components/ui/IngestForm'
import { formatDate, formatNumber } from '../lib/wow-classes'

export default function DashboardPage() {
  const { data: stats, refetch: refetchStats } = useApiQuery(
    () => getDashboardStats(), [],
  )
  const { data: recent, refetch: refetchRecent } = useApiQuery(
    () => getDashboardRecent(), [],
  )

  const handleIngested = () => {
    refetchStats()
    refetchRecent()
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Dashboard</h1>

      {/* Stats row */}
      {stats && (
        <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Reports</p>
            <p className="mt-1 text-lg font-bold text-zinc-100">{stats.total_reports}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Kills</p>
            <p className="mt-1 text-lg font-bold text-emerald-500">{stats.total_kills}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Wipes</p>
            <p className={`mt-1 text-lg font-bold ${stats.total_wipes > 0 ? 'text-red-400' : 'text-zinc-300'}`}>
              {stats.total_wipes}
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Characters</p>
            <p className="mt-1 text-lg font-bold text-zinc-100">{stats.total_characters}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <p className="text-xs font-medium text-zinc-500">Encounters</p>
            <p className="mt-1 text-lg font-bold text-zinc-100">{stats.total_encounters}</p>
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="mb-8 flex flex-wrap gap-3">
        <Link
          to="/chat"
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-zinc-700"
        >
          <MessageSquare className="h-4 w-4" />
          Ask the Agent
        </Link>
        <Link
          to="/reports"
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-zinc-700"
        >
          <FileText className="h-4 w-4" />
          View Reports
        </Link>
        <Link
          to="/characters"
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-zinc-700"
        >
          <Users className="h-4 w-4" />
          Characters
        </Link>
      </div>

      {/* Ingest form */}
      <div className="mb-8">
        <h2 className="mb-3 text-lg font-semibold text-zinc-200">Ingest Report</h2>
        <IngestForm onIngested={handleIngested} />
      </div>

      {/* Recent reports */}
      <h2 className="mb-4 text-lg font-semibold text-zinc-200">Recent Reports</h2>
      {recent && recent.length > 0 ? (
        <div className="space-y-2">
          {recent.map((r) => (
            <Link
              key={r.code}
              to={`/reports/${r.code}`}
              className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/50 px-5 py-4 transition-colors hover:border-zinc-700 hover:bg-zinc-900"
            >
              <div>
                <p className="font-semibold text-zinc-100">{r.title}</p>
                <p className="mt-0.5 text-sm text-zinc-400">
                  {formatDate(r.start_time)}
                  {r.guild_name && <> &middot; {r.guild_name}</>}
                  {' '}&middot; {r.code}
                </p>
              </div>
              <div className="flex items-center gap-6 text-sm">
                <div className="flex items-center gap-1.5 text-zinc-400">
                  <Swords className="h-3.5 w-3.5" />
                  <span>{r.fight_count} fights</span>
                </div>
                <div className="flex items-center gap-1.5 text-emerald-500">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>{r.kill_count} kills</span>
                </div>
                {r.wipe_count > 0 && (
                  <div className="flex items-center gap-1.5 text-red-400">
                    <Skull className="h-3.5 w-3.5" />
                    <span>{r.wipe_count} wipes</span>
                  </div>
                )}
                {r.avg_kill_dps != null && (
                  <span className="text-zinc-300">{formatNumber(r.avg_kill_dps)} avg DPS</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-zinc-800 p-8 text-center text-sm text-zinc-500">
          No reports yet. Ingest a report above to get started.
        </div>
      )}
    </div>
  )
}
