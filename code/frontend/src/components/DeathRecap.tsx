import { Skull } from 'lucide-react'
import type { DeathDetail } from '../lib/types'

interface DeathEvent {
  ts: number
  ability: string
  amount: number
  source: string
  type: string
}

interface Props {
  deaths: DeathDetail[]
}

function formatTimestamp(ms: number): string {
  const sec = ms / 1000
  const m = Math.floor(sec / 60)
  const s = (sec % 60).toFixed(1)
  return `${m}:${s.padStart(4, '0')}`
}

export default function DeathRecap({ deaths }: Props) {
  if (deaths.length === 0) return null

  return (
    <div className="space-y-4">
      {deaths.map((death, idx) => {
        let events: DeathEvent[] = []
        try {
          events = JSON.parse(death.events_json) as DeathEvent[]
        } catch {
          // ignore malformed JSON
        }

        return (
          <div
            key={`${death.player_name}-${death.death_index}-${idx}`}
            className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4"
          >
            {/* Header */}
            <div className="mb-3 flex items-center gap-2">
              <Skull className="h-4 w-4 text-red-400" />
              <span className="font-medium text-zinc-200">
                {death.player_name}
              </span>
              <span className="text-xs text-zinc-500">
                death #{death.death_index} at {formatTimestamp(death.timestamp_ms)}
              </span>
            </div>

            {/* Killing blow */}
            <div className="mb-3 rounded-md border border-red-900/40 bg-red-950/20 px-3 py-2">
              <p className="text-sm font-medium text-red-400">
                {death.killing_blow_ability}
              </p>
              <p className="text-xs text-red-400/70">
                from {death.killing_blow_source} &middot; Total damage taken: {death.damage_taken_total.toLocaleString()}
              </p>
            </div>

            {/* Event timeline */}
            {events.length > 0 && (
              <div className="space-y-1">
                <p className="mb-1 text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Last damage events
                </p>
                {events.map((e, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 rounded px-2 py-1 text-xs hover:bg-zinc-800/50"
                  >
                    <span className="w-12 shrink-0 font-mono text-zinc-500">
                      {formatTimestamp(e.ts)}
                    </span>
                    <span className="flex-1 text-zinc-300">{e.ability}</span>
                    <span className="font-mono text-red-400">
                      -{e.amount.toLocaleString()}
                    </span>
                    <span className="w-24 truncate text-right text-zinc-500">
                      {e.source}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
