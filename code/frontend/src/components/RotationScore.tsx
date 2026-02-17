import type { RotationScoreEntry } from '../lib/types'

interface Props {
  data: RotationScoreEntry
}

function scoreColor(pct: number): string {
  if (pct >= 90) return '#22c55e'
  if (pct >= 75) return '#84cc16'
  if (pct >= 60) return '#eab308'
  return '#ef4444'
}

function scoreGrade(pct: number): string {
  if (pct >= 90) return 'A'
  if (pct >= 80) return 'B'
  if (pct >= 70) return 'C'
  if (pct >= 60) return 'D'
  return 'F'
}

interface Violation {
  rule: string
  actual: number
  threshold: number
}

export default function RotationScoreComponent({ data }: Props) {
  const color = scoreColor(data.score_pct)
  const grade = scoreGrade(data.score_pct)

  let violations: Violation[] = []
  if (data.violations_json) {
    try {
      violations = JSON.parse(data.violations_json)
    } catch {
      // ignore parse errors
    }
  }

  const radius = 50
  const circumference = 2 * Math.PI * radius
  const pct = Math.min(data.score_pct, 100)
  const dashOffset = circumference - (pct / 100) * circumference

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start sm:gap-8">
      {/* Circular score */}
      <div className="relative flex shrink-0 items-center justify-center">
        <svg width="130" height="130" viewBox="0 0 130 130">
          <circle cx="65" cy="65" r={radius} fill="none" stroke="#27272a" strokeWidth="8" />
          <circle
            cx="65"
            cy="65"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            transform="rotate(-90 65 65)"
            className="transition-all duration-700"
          />
        </svg>
        <div className="absolute flex flex-col items-center">
          <span className="text-3xl font-bold" style={{ color }}>
            {grade}
          </span>
          <span className="text-xs text-zinc-400">
            {data.score_pct.toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Details */}
      <div className="flex-1 space-y-3">
        <div className="text-sm text-zinc-300">
          <span className="font-medium">{data.rules_passed}</span>
          <span className="text-zinc-500"> / {data.rules_checked} rules passed</span>
          {data.spec && (
            <span className="ml-2 text-zinc-500">({data.spec})</span>
          )}
        </div>

        {violations.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-zinc-500">Issues:</p>
            {violations.map((v, i) => (
              <div
                key={i}
                className="flex items-center gap-2 rounded bg-red-950/20 px-3 py-1.5 text-xs"
              >
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-red-400" />
                <span className="text-zinc-300">{v.rule}</span>
                <span className="ml-auto font-mono text-red-400">
                  {typeof v.actual === 'number' ? v.actual.toFixed(1) : v.actual}
                </span>
                <span className="text-zinc-500">
                  (need {typeof v.threshold === 'number' ? `≥${v.threshold}` : v.threshold})
                </span>
              </div>
            ))}
          </div>
        )}

        {violations.length === 0 && (
          <p className="text-xs text-emerald-400/80">All rotation checks passed!</p>
        )}
      </div>
    </div>
  )
}
