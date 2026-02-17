import type { CancelledCastSummary } from '../lib/types'

interface Props {
  data: CancelledCastSummary
}

export default function CancelledCasts({ data }: Props) {
  const grade =
    data.cancel_pct < 5
      ? { label: 'Excellent', color: 'text-emerald-400' }
      : data.cancel_pct < 10
        ? { label: 'Good', color: 'text-blue-400' }
        : data.cancel_pct < 20
          ? { label: 'Fair', color: 'text-amber-400' }
          : { label: 'Needs Work', color: 'text-red-400' }

  let topCancelled: { spell_id: number; count: number }[] = []
  if (data.top_cancelled_json) {
    try {
      topCancelled = JSON.parse(data.top_cancelled_json)
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <p className="text-xs text-zinc-500">Cast Begins</p>
          <p className="font-mono text-lg font-bold text-zinc-200">
            {data.total_begins}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Completed</p>
          <p className="font-mono text-lg font-bold text-zinc-200">
            {data.total_completions}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Cancelled</p>
          <p className={`font-mono text-lg font-bold ${data.cancel_count > 0 ? 'text-amber-400' : 'text-zinc-200'}`}>
            {data.cancel_count}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Cancel Rate</p>
          <p className={`text-lg font-bold ${grade.color}`}>
            {data.cancel_pct.toFixed(1)}%
          </p>
          <p className={`text-xs ${grade.color}`}>{grade.label}</p>
        </div>
      </div>

      {topCancelled.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-zinc-500">
            Most Cancelled (by Spell ID)
          </p>
          <div className="space-y-1">
            {topCancelled.map((c) => (
              <div
                key={c.spell_id}
                className="flex items-center justify-between rounded bg-zinc-800/50 px-2 py-1 text-sm"
              >
                <span className="text-zinc-300">Spell #{c.spell_id}</span>
                <span className="font-mono text-amber-400">{c.count}x</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
