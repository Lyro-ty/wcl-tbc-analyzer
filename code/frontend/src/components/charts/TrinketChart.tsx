import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts'
import type { TrinketProc } from '../../lib/types'

interface Props {
  data: TrinketProc[]
}

const GRADE_COLORS: Record<string, string> = {
  GOOD: '#22c55e',
  OK: '#eab308',
  LOW: '#ef4444',
  UNKNOWN: '#71717a',
}

export default function TrinketChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        No known trinket procs detected. The player may not have recognized
        trinkets equipped, or table data may not have been ingested.
      </p>
    )
  }

  const chartData = data.map((t) => ({
    name: t.trinket_name.length > 25
      ? t.trinket_name.slice(0, 23) + '\u2026'
      : t.trinket_name,
    uptime: t.uptime_pct,
    expected: t.expected_uptime_pct,
    grade: t.grade,
  }))

  return (
    <div className="space-y-3">
      <ResponsiveContainer width="100%" height={Math.max(120, data.length * 50)}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 30 }}>
          <XAxis
            type="number"
            domain={[0, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fill: '#a1a1aa', fontSize: 12 }}
          />
          <YAxis
            dataKey="name"
            type="category"
            width={180}
            tick={{ fill: '#d4d4d8', fontSize: 12 }}
          />
          <Tooltip
            contentStyle={{ background: '#27272a', border: '1px solid #3f3f46' }}
            formatter={(value: number, _name: string, entry: { payload: { expected: number; grade: string } }) => [
              `${value.toFixed(1)}% (expected ~${entry.payload.expected}%) [${entry.payload.grade}]`,
              'Uptime',
            ]}
          />
          <Bar dataKey="uptime" radius={[0, 4, 4, 0]}>
            {chartData.map((entry, idx) => (
              <Cell key={idx} fill={GRADE_COLORS[entry.grade] ?? '#71717a'} />
            ))}
          </Bar>
          {chartData.length > 0 && chartData[0].expected > 0 && (
            <ReferenceLine
              x={chartData[0].expected}
              stroke="#71717a"
              strokeDasharray="4 4"
              label={{ value: 'Expected', fill: '#71717a', fontSize: 11 }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>

      <div className="flex gap-4 text-xs text-zinc-400">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded" style={{ background: '#22c55e' }} />
          Good
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded" style={{ background: '#eab308' }} />
          OK
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded" style={{ background: '#ef4444' }} />
          Low
        </span>
      </div>
    </div>
  )
}
