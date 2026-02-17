import type { RotationScoreEntry } from '../lib/types'

interface Props {
  data: RotationScoreEntry
}

interface Violation {
  rule: string
  description: string
  actual: number
  expected: number
  detail: string
}

export default function RotationScore({ data }: Props) {
  const violations: Violation[] = data.violations_json
    ? JSON.parse(data.violations_json)
    : []

  const grade =
    data.score_pct >= 90
      ? { letter: 'A', color: 'text-emerald-400', bg: 'bg-emerald-500/20' }
      : data.score_pct >= 75
        ? { letter: 'B', color: 'text-blue-400', bg: 'bg-blue-500/20' }
        : data.score_pct >= 50
          ? { letter: 'C', color: 'text-amber-400', bg: 'bg-amber-500/20' }
          : data.score_pct >= 25
            ? { letter: 'D', color: 'text-orange-400', bg: 'bg-orange-500/20' }
            : { letter: 'F', color: 'text-red-400', bg: 'bg-red-500/20' }

  return (
    <div className="space-y-4">
      {/* Score header */}
      <div className="flex items-center gap-4">
        <div
          className={`flex h-16 w-16 items-center justify-center rounded-xl ${grade.bg}`}
        >
          <span className={`text-3xl font-black ${grade.color}`}>
            {grade.letter}
          </span>
        </div>
        <div>
          <p className="text-lg font-bold text-zinc-200">
            {data.score_pct.toFixed(0)}% — {data.spec} Rotation
          </p>
          <p className="text-sm text-zinc-400">
            {data.rules_passed}/{data.rules_checked} rules passed
          </p>
        </div>
      </div>

      {/* Violations list */}
      {violations.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium uppercase tracking-wider text-zinc-500">
            Issues Found
          </h4>
          {violations.map((v, i) => (
            <div
              key={i}
              className="rounded-lg border border-red-900/30 bg-red-950/10 p-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-zinc-200">
                  {v.rule}
                </span>
                <span className="text-xs text-red-400">{v.detail}</span>
              </div>
              <p className="mt-1 text-xs text-zinc-400">{v.description}</p>
            </div>
          ))}
        </div>
      )}

      {/* All passed */}
      {violations.length === 0 && data.rules_checked > 0 && (
        <p className="text-sm text-emerald-400">
          All rotation rules passed. Excellent play!
        </p>
      )}
    </div>
  )
}
