import type { CastMetricSummary } from '../../lib/types'
import { formatDuration } from '../../lib/wow-classes'

interface Props {
  data: CastMetricSummary
}

function gradeColor(pct: number): string {
  if (pct >= 90) return '#22c55e'
  if (pct >= 85) return '#84cc16'
  if (pct >= 75) return '#eab308'
  return '#ef4444'
}

function gradeLabel(pct: number): string {
  if (pct >= 90) return 'EXCELLENT'
  if (pct >= 85) return 'GOOD'
  if (pct >= 75) return 'FAIR'
  return 'NEEDS WORK'
}

export default function ActivityGauge({ data }: Props) {
  const color = gradeColor(data.gcd_uptime_pct)
  const grade = gradeLabel(data.gcd_uptime_pct)

  // SVG arc for the gauge
  const radius = 60
  const circumference = 2 * Math.PI * radius
  const pct = Math.min(data.gcd_uptime_pct, 100)
  const dashOffset = circumference - (pct / 100) * circumference

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start sm:gap-8">
      {/* Circular gauge */}
      <div className="relative flex shrink-0 items-center justify-center">
        <svg width="150" height="150" viewBox="0 0 150 150">
          {/* Background circle */}
          <circle
            cx="75"
            cy="75"
            r={radius}
            fill="none"
            stroke="#27272a"
            strokeWidth="10"
          />
          {/* Progress arc */}
          <circle
            cx="75"
            cy="75"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            transform="rotate(-90 75 75)"
            className="transition-all duration-700"
          />
        </svg>
        <div className="absolute flex flex-col items-center">
          <span className="text-2xl font-bold" style={{ color }}>
            {data.gcd_uptime_pct.toFixed(1)}%
          </span>
          <span className="text-xs font-medium" style={{ color }}>
            {grade}
          </span>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <div>
          <p className="text-xs text-zinc-500">Total Casts</p>
          <p className="font-mono font-medium text-zinc-200">{data.total_casts}</p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Casts/min</p>
          <p className="font-mono font-medium text-zinc-200">{data.casts_per_minute}</p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Active Time</p>
          <p className="font-mono font-medium text-zinc-200">
            {formatDuration(data.active_time_ms)}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Downtime</p>
          <p className="font-mono font-medium text-zinc-200">
            {formatDuration(data.downtime_ms)}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Longest Gap</p>
          <p className="font-mono font-medium text-zinc-200">
            {data.longest_gap_ms > 0 ? formatDuration(data.longest_gap_ms) : 'none'}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Gaps &gt;2.5s</p>
          <p className="font-mono font-medium text-zinc-200">{data.gap_count}</p>
        </div>
      </div>
    </div>
  )
}
