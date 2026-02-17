import type { CooldownWindowEntry } from '../../lib/types'

interface Props {
  data: CooldownWindowEntry[]
  fightDurationMs: number
}

export default function CooldownWindowChart({ data, fightDurationMs }: Props) {
  if (data.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        No cooldown window data available.
      </p>
    )
  }

  const totalSec = fightDurationMs / 1000

  return (
    <div className="space-y-3">
      {/* Baseline DPS */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-zinc-500">Baseline DPS:</span>
        <span className="font-mono font-bold text-zinc-200">
          {data[0]?.baseline_dps.toLocaleString() ?? '—'}
        </span>
      </div>

      {/* Timeline + table hybrid */}
      {data.map((w, i) => {
        const startPct =
          (w.window_start_ms / fightDurationMs) * 100
        const widthPct =
          ((w.window_end_ms - w.window_start_ms) / fightDurationMs) *
          100
        const gainPositive = w.dps_gain_pct > 0

        return (
          <div key={`${w.spell_id}-${i}`} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-zinc-300">
                {w.ability_name}
              </span>
              <div className="flex items-center gap-3">
                <span className="font-mono text-zinc-400">
                  {(w.window_start_ms / 1000).toFixed(0)}s
                  {' – '}
                  {(w.window_end_ms / 1000).toFixed(0)}s
                </span>
                <span className="font-mono font-bold text-zinc-200">
                  {w.window_dps.toLocaleString()} DPS
                </span>
                <span
                  className={`font-mono font-bold ${
                    gainPositive
                      ? 'text-emerald-400'
                      : 'text-red-400'
                  }`}
                >
                  {gainPositive ? '+' : ''}
                  {w.dps_gain_pct.toFixed(1)}%
                </span>
              </div>
            </div>

            {/* Visual timeline bar */}
            <div className="relative h-3 rounded bg-zinc-800/50">
              <div
                className={`absolute h-full rounded ${
                  gainPositive
                    ? 'bg-emerald-500/40'
                    : 'bg-red-500/40'
                }`}
                style={{
                  left: `${startPct}%`,
                  width: `${Math.min(widthPct, 100 - startPct)}%`,
                }}
              />
            </div>
          </div>
        )
      })}

      <p className="text-[10px] text-zinc-600">
        {data.length} cooldown window{data.length !== 1 ? 's' : ''} across{' '}
        {totalSec.toFixed(0)}s fight
      </p>
    </div>
  )
}
