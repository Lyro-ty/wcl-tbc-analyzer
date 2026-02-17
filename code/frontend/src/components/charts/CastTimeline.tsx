import { useMemo, useState } from 'react'
import type { CastEventEntry } from '../../lib/types'

interface Props {
  data: CastEventEntry[]
  fightDurationMs: number
}

function getAbilityColor(index: number): string {
  const colors = [
    '#ef4444', '#f97316', '#eab308', '#22c55e',
    '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899',
    '#f43f5e', '#14b8a6', '#a855f7', '#6366f1',
  ]
  return colors[index % colors.length]
}

export default function CastTimeline({ data, fightDurationMs }: Props) {
  const [hoveredEvent, setHoveredEvent] = useState<CastEventEntry | null>(null)

  const { lanes, abilityColors } = useMemo(() => {
    // Group events by ability name to create lanes
    const abilityMap = new Map<string, CastEventEntry[]>()
    for (const evt of data) {
      if (evt.event_type !== 'cast') continue
      const existing = abilityMap.get(evt.ability_name) ?? []
      existing.push(evt)
      abilityMap.set(evt.ability_name, existing)
    }

    // Sort lanes by total casts descending
    const sorted = [...abilityMap.entries()]
      .sort((a, b) => b[1].length - a[1].length)
      .slice(0, 15) // Top 15 abilities

    const colors: Record<string, string> = {}
    sorted.forEach(([name], i) => {
      colors[name] = getAbilityColor(i)
    })

    return { lanes: sorted, abilityColors: colors }
  }, [data])

  if (data.length === 0) {
    return (
      <p className="text-sm text-zinc-500">No cast events available.</p>
    )
  }

  const totalSec = fightDurationMs / 1000
  // Generate time markers every 30s
  const markers: number[] = []
  for (let t = 0; t <= totalSec; t += 30) {
    markers.push(t)
  }

  return (
    <div className="space-y-1">
      {/* Time axis */}
      <div className="relative ml-32 h-5 border-b border-zinc-800">
        {markers.map((t) => (
          <span
            key={t}
            className="absolute -translate-x-1/2 text-[10px] text-zinc-600"
            style={{ left: `${(t / totalSec) * 100}%` }}
          >
            {Math.floor(t / 60)}:{String(Math.floor(t % 60)).padStart(2, '0')}
          </span>
        ))}
      </div>

      {/* Lanes */}
      {lanes.map(([abilityName, events]) => (
        <div key={abilityName} className="flex items-center gap-2">
          <div
            className="w-32 truncate text-right text-xs text-zinc-400"
            title={abilityName}
          >
            {abilityName}
          </div>
          <div className="relative h-5 flex-1 rounded bg-zinc-900/50">
            {events.map((evt, i) => {
              const pct = (evt.timestamp_ms / fightDurationMs) * 100
              return (
                <div
                  key={`${evt.timestamp_ms}-${i}`}
                  className="absolute top-0.5 h-4 w-1 rounded-sm opacity-80 transition-opacity hover:opacity-100"
                  style={{
                    left: `${pct}%`,
                    backgroundColor: abilityColors[abilityName],
                  }}
                  onMouseEnter={() => setHoveredEvent(evt)}
                  onMouseLeave={() => setHoveredEvent(null)}
                />
              )
            })}
          </div>
        </div>
      ))}

      {/* Tooltip */}
      {hoveredEvent && (
        <div className="mt-2 rounded bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300">
          <span className="font-medium text-zinc-100">
            {hoveredEvent.ability_name}
          </span>
          {' at '}
          {(hoveredEvent.timestamp_ms / 1000).toFixed(1)}s
          {hoveredEvent.target_name && (
            <span className="text-zinc-500"> &rarr; {hoveredEvent.target_name}</span>
          )}
        </div>
      )}

      <p className="mt-1 text-[10px] text-zinc-600">
        Showing top {lanes.length} abilities ({data.filter(e => e.event_type === 'cast').length} casts total)
      </p>
    </div>
  )
}
