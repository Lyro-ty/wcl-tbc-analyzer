import type { TrinketProc } from '../../lib/types'

interface Props {
  data: TrinketProc[]
}

function gradeColor(grade: string): string {
  switch (grade) {
    case 'EXCELLENT':
      return '#22c55e'
    case 'GOOD':
      return '#84cc16'
    case 'POOR':
      return '#ef4444'
    default:
      return '#71717a'
  }
}

export default function TrinketChart({ data }: Props) {
  if (data.length === 0) return null

  return (
    <div className="space-y-3">
      {data.map((t, i) => {
        const color = gradeColor(t.grade)
        const pct = Math.min(t.uptime_pct, 100)
        const expectedPct = Math.min(t.expected_uptime_pct, 100)

        return (
          <div
            key={i}
            className="rounded-lg border border-zinc-800/50 bg-zinc-900/30 p-3"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-zinc-200">{t.trinket_name}</span>
              <span
                className="rounded px-2 py-0.5 text-xs font-bold"
                style={{ color, backgroundColor: `${color}15` }}
              >
                {t.grade}
              </span>
            </div>

            {/* Uptime bars */}
            <div className="space-y-1.5">
              <div>
                <div className="mb-0.5 flex items-center justify-between text-xs">
                  <span className="text-zinc-500">Actual Uptime</span>
                  <span className="font-mono" style={{ color }}>
                    {t.uptime_pct.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${pct}%`, backgroundColor: color }}
                  />
                </div>
              </div>
              <div>
                <div className="mb-0.5 flex items-center justify-between text-xs">
                  <span className="text-zinc-500">Expected Uptime</span>
                  <span className="font-mono text-zinc-400">
                    {t.expected_uptime_pct.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
                  <div
                    className="h-full rounded-full bg-zinc-600 transition-all duration-500"
                    style={{ width: `${expectedPct}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
