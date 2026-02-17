import { CheckCircle2, XCircle } from 'lucide-react'
import type { ConsumablePlayerEntry } from '../lib/types'

interface Props {
  data: ConsumablePlayerEntry
}

export default function ConsumableCheck({ data }: Props) {
  const total = data.consumables.length + data.missing.length
  const scorePct = total > 0 ? (data.consumables.length / total) * 100 : 0
  const scoreColor =
    scorePct >= 80
      ? 'text-emerald-400'
      : scorePct >= 50
        ? 'text-amber-400'
        : 'text-red-400'

  return (
    <div className="space-y-4">
      {/* Score header */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-400">{data.player_name}</p>
        <p className={`text-lg font-bold ${scoreColor}`}>
          {scorePct.toFixed(0)}% Prep Score
        </p>
      </div>

      {/* Present */}
      {data.consumables.length > 0 && (
        <div className="space-y-1">
          {data.consumables.map((c) => (
            <div
              key={`${c.spell_id}`}
              className="flex items-center gap-2 rounded px-2 py-1 text-sm"
            >
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
              <span className="flex-1 text-zinc-200">{c.ability_name}</span>
              <span className="text-xs text-zinc-500">{c.category}</span>
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
          {data.missing.map((cat) => (
            <div
              key={cat}
              className="flex items-center gap-2 rounded bg-red-950/20 px-2 py-1 text-sm"
            >
              <XCircle className="h-4 w-4 shrink-0 text-red-400" />
              <span className="flex-1 text-zinc-300">{cat}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
