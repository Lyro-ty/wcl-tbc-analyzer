import type { PhaseMetricEntry } from '../../lib/types'
import { formatDuration } from '../../lib/wow-classes'

interface Props {
  data: PhaseMetricEntry[]
  fightDurationMs: number
}

const PHASE_COLORS = [
  '#6366f1', // indigo
  '#8b5cf6', // violet
  '#a855f7', // purple
  '#c084fc', // purple-light
  '#818cf8', // indigo-light
  '#60a5fa', // blue
]

export default function PhaseBreakdown({ data, fightDurationMs }: Props) {
  if (data.length === 0) return null

  return (
    <div className="space-y-4">
      {/* Timeline bar */}
      {fightDurationMs > 0 && (
        <div className="flex h-6 w-full overflow-hidden rounded-lg">
          {data.map((phase, i) => {
            const duration = phase.phase_end_ms - phase.phase_start_ms
            const widthPct = (duration / fightDurationMs) * 100
            return (
              <div
                key={i}
                className="flex items-center justify-center text-[10px] font-medium text-white/90"
                style={{
                  width: `${widthPct}%`,
                  backgroundColor: phase.is_downtime
                    ? '#27272a'
                    : PHASE_COLORS[i % PHASE_COLORS.length],
                  opacity: phase.is_downtime ? 0.5 : 0.8,
                }}
                title={`${phase.phase_name}: ${formatDuration(duration)}`}
              >
                {widthPct > 8 ? phase.phase_name : ''}
              </div>
            )
          })}
        </div>
      )}

      {/* Phase detail cards */}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {data.map((phase, i) => {
          const duration = phase.phase_end_ms - phase.phase_start_ms
          return (
            <div
              key={i}
              className={`rounded-lg border p-3 ${
                phase.is_downtime
                  ? 'border-zinc-800/50 bg-zinc-900/20'
                  : 'border-zinc-800 bg-zinc-900/40'
              }`}
            >
              <div className="mb-2 flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{
                    backgroundColor: phase.is_downtime
                      ? '#52525b'
                      : PHASE_COLORS[i % PHASE_COLORS.length],
                  }}
                />
                <span className="text-sm font-medium text-zinc-200">{phase.phase_name}</span>
                {phase.is_downtime && (
                  <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-500">
                    DOWNTIME
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <div>
                  <span className="text-zinc-500">Duration</span>
                  <p className="font-mono text-zinc-300">{formatDuration(duration)}</p>
                </div>
                {phase.phase_dps != null && (
                  <div>
                    <span className="text-zinc-500">DPS</span>
                    <p className="font-mono text-zinc-300">
                      {Math.round(phase.phase_dps).toLocaleString()}
                    </p>
                  </div>
                )}
                {phase.phase_casts != null && (
                  <div>
                    <span className="text-zinc-500">Casts</span>
                    <p className="font-mono text-zinc-300">{phase.phase_casts}</p>
                  </div>
                )}
                {phase.phase_gcd_uptime_pct != null && (
                  <div>
                    <span className="text-zinc-500">GCD Uptime</span>
                    <p className="font-mono text-zinc-300">
                      {phase.phase_gcd_uptime_pct.toFixed(1)}%
                    </p>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
