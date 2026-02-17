import type { DotRefreshEntry } from '../../lib/types'

interface Props {
  data: DotRefreshEntry[]
}

export default function DotRefreshChart({ data }: Props) {
  return (
    <div className="space-y-3">
      {data.map((dot) => {
        const grade =
          dot.early_refresh_pct <= 5
            ? { label: 'EXCELLENT', color: 'text-emerald-400' }
            : dot.early_refresh_pct <= 15
              ? { label: 'GOOD', color: 'text-blue-400' }
              : dot.early_refresh_pct <= 30
                ? { label: 'FAIR', color: 'text-amber-400' }
                : { label: 'POOR', color: 'text-red-400' }

        return (
          <div
            key={dot.spell_id}
            className="rounded-lg border border-zinc-700 bg-zinc-900/50 p-3"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-zinc-200">
                {dot.ability_name}
              </span>
              <span className={`text-xs font-bold ${grade.color}`}>
                [{grade.label}]
              </span>
            </div>
            <div className="mt-2 grid grid-cols-4 gap-3 text-xs">
              <div>
                <span className="text-zinc-500">Refreshes</span>
                <p className="font-mono text-zinc-200">{dot.total_refreshes}</p>
              </div>
              <div>
                <span className="text-zinc-500">Early</span>
                <p className="font-mono text-red-400">
                  {dot.early_refreshes} ({dot.early_refresh_pct}%)
                </p>
              </div>
              <div>
                <span className="text-zinc-500">Avg Remaining</span>
                <p className="font-mono text-zinc-200">
                  {(dot.avg_remaining_ms / 1000).toFixed(1)}s
                </p>
              </div>
              <div>
                <span className="text-zinc-500">Clipped Ticks</span>
                <p className="font-mono text-orange-400">
                  ~{dot.clipped_ticks_est}
                </p>
              </div>
            </div>
            {/* Progress bar showing early vs total */}
            <div className="mt-2">
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-red-500 to-orange-500"
                  style={{
                    width: `${Math.min(dot.early_refresh_pct, 100)}%`,
                  }}
                />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
