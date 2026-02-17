import { CheckCircle2, XCircle } from 'lucide-react'
import type { ConsumableCheck as ConsumableCheckType } from '../lib/types'

interface Props {
  data: ConsumableCheckType
}

export default function ConsumableCheck({ data }: Props) {
  const scoreColor =
    data.score_pct >= 80
      ? 'text-emerald-400'
      : data.score_pct >= 50
        ? 'text-amber-400'
        : 'text-red-400'

  return (
    <div className="space-y-4">
      {/* Score header */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-400">
          {data.player_spec} ({data.role})
        </p>
        <p className={`text-lg font-bold ${scoreColor}`}>
          {data.score_pct.toFixed(0)}% Prep Score
        </p>
      </div>

      {/* Present */}
      {data.present.length > 0 && (
        <div className="space-y-1">
          {data.present.map((c) => (
            <div
              key={c.name}
              className="flex items-center gap-2 rounded px-2 py-1 text-sm"
            >
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
              <span className="flex-1 text-zinc-200">{c.name}</span>
              <span className="text-xs text-zinc-500">{c.category}</span>
              {c.uptime_pct != null && (
                <span className="font-mono text-xs text-zinc-400">
                  {c.uptime_pct.toFixed(1)}%
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Missing */}
      {data.missing.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wider text-red-400/80">
            Missing
          </p>
          {data.missing.map((c) => (
            <div
              key={c.name}
              className="flex items-center gap-2 rounded bg-red-950/20 px-2 py-1 text-sm"
            >
              <XCircle className="h-4 w-4 shrink-0 text-red-400" />
              <span className="flex-1 text-zinc-300">{c.name}</span>
              <span className="text-xs text-zinc-500">{c.category}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
