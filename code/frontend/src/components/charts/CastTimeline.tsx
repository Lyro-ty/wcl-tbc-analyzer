import { useMemo, useState } from 'react'
import type { CastEventEntry } from '../../lib/types'
import { formatDuration } from '../../lib/wow-classes'

interface Props {
  data: CastEventEntry[]
  fightDurationMs: number
}

export default function CastTimeline({ data, fightDurationMs }: Props) {
  const [filter, setFilter] = useState('')

  // Group by ability for legend/filter
  const abilities = useMemo(() => {
    const map = new Map<string, number>()
    for (const e of data) {
      if (e.event_type === 'cast') {
        map.set(e.ability_name, (map.get(e.ability_name) ?? 0) + 1)
      }
    }
    return [...map.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ name, count }))
  }, [data])

  const filteredData = useMemo(() => {
    if (!filter) return data.filter((e) => e.event_type === 'cast')
    return data.filter((e) => e.event_type === 'cast' && e.ability_name === filter)
  }, [data, filter])

  // Assign colors to abilities
  const COLORS = [
    '#ef4444', '#3b82f6', '#22c55e', '#eab308', '#a855f7',
    '#f97316', '#06b6d4', '#ec4899', '#84cc16', '#6366f1',
    '#14b8a6', '#f43f5e',
  ]
  const colorMap = useMemo(() => {
    const m = new Map<string, string>()
    abilities.forEach((a, i) => m.set(a.name, COLORS[i % COLORS.length]))
    return m
  }, [abilities])

  const minTs = data.length > 0 ? Math.min(...data.map((d) => d.timestamp_ms)) : 0

  return (
    <div>
      {/* Ability filter chips */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        <button
          onClick={() => setFilter('')}
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
            !filter
              ? 'bg-zinc-700 text-zinc-100'
              : 'bg-zinc-800/50 text-zinc-400 hover:bg-zinc-800'
          }`}
        >
          All ({data.filter((e) => e.event_type === 'cast').length})
        </button>
        {abilities.slice(0, 12).map((a) => (
          <button
            key={a.name}
            onClick={() => setFilter(filter === a.name ? '' : a.name)}
            className={`flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
              filter === a.name
                ? 'bg-zinc-700 text-zinc-100'
                : 'bg-zinc-800/50 text-zinc-400 hover:bg-zinc-800'
            }`}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: colorMap.get(a.name) }}
            />
            {a.name} ({a.count})
          </button>
        ))}
      </div>

      {/* Timeline visualization */}
      {fightDurationMs > 0 && (
        <div className="relative mb-3 h-8 w-full overflow-hidden rounded bg-zinc-900">
          {filteredData.map((e, i) => {
            const leftPct = ((e.timestamp_ms - minTs) / fightDurationMs) * 100
            return (
              <div
                key={i}
                className="absolute top-0 h-full"
                style={{
                  left: `${leftPct}%`,
                  width: '2px',
                  backgroundColor: colorMap.get(e.ability_name) ?? '#71717a',
                  opacity: 0.6,
                }}
                title={`${e.ability_name} @ ${formatDuration(e.timestamp_ms - minTs)}`}
              />
            )
          })}
        </div>
      )}

      {/* Cast list */}
      <div className="max-h-64 overflow-y-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800 text-left text-zinc-500">
              <th className="py-1.5 pr-3 font-medium">Time</th>
              <th className="py-1.5 pr-3 font-medium">Ability</th>
              <th className="py-1.5 font-medium">Target</th>
            </tr>
          </thead>
          <tbody>
            {filteredData.slice(0, 200).map((e, i) => (
              <tr key={i} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                <td className="py-1 pr-3 font-mono text-zinc-400">
                  {formatDuration(e.timestamp_ms - minTs)}
                </td>
                <td className="py-1 pr-3">
                  <span className="flex items-center gap-1.5">
                    <span
                      className="h-1.5 w-1.5 rounded-full"
                      style={{ backgroundColor: colorMap.get(e.ability_name) ?? '#71717a' }}
                    />
                    <span className="text-zinc-200">{e.ability_name}</span>
                  </span>
                </td>
                <td className="py-1 text-zinc-500">{e.target_name ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredData.length > 200 && (
          <p className="mt-2 text-center text-xs text-zinc-500">
            Showing first 200 of {filteredData.length} casts
          </p>
        )}
      </div>
    </div>
  )
}
