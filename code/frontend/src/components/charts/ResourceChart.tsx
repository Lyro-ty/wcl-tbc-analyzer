import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ResourceSnapshot } from '../../lib/types'

interface Props {
  data: ResourceSnapshot
}

const RESOURCE_COLORS: Record<string, string> = {
  mana: '#3b82f6',
  rage: '#ef4444',
  energy: '#eab308',
  focus: '#22c55e',
}

export default function ResourceChart({ data }: Props) {
  const chartData = useMemo(() => {
    if (!data.samples_json) return []
    try {
      const samples: { t: number; v: number }[] = JSON.parse(
        data.samples_json,
      )
      return samples.map((s) => ({
        time: Math.round(s.t / 1000),
        value: s.v,
      }))
    } catch {
      return []
    }
  }, [data.samples_json])

  const color = RESOURCE_COLORS[data.resource_type] ?? '#a3a3a3'
  const label = data.resource_type.charAt(0).toUpperCase()
    + data.resource_type.slice(1)

  return (
    <div className="space-y-3">
      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div>
          <p className="text-xs text-zinc-500">Resource</p>
          <p className="font-mono text-sm font-bold text-zinc-200">
            {label}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Min</p>
          <p className="font-mono text-sm font-bold text-zinc-200">
            {data.min_value.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Max</p>
          <p className="font-mono text-sm font-bold text-zinc-200">
            {data.max_value.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Average</p>
          <p className="font-mono text-sm font-bold text-zinc-200">
            {data.avg_value.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-500">Time at 0</p>
          <p className={`font-mono text-sm font-bold ${data.time_at_zero_pct > 10 ? 'text-red-400' : 'text-zinc-200'}`}>
            {data.time_at_zero_pct.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={chartData}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#27272a"
            />
            <XAxis
              dataKey="time"
              tick={{ fill: '#71717a', fontSize: 10 }}
              tickFormatter={(v: number) =>
                `${Math.floor(v / 60)}:${String(v % 60).padStart(2, '0')}`
              }
            />
            <YAxis
              tick={{ fill: '#71717a', fontSize: 10 }}
              width={50}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#18181b',
                border: '1px solid #3f3f46',
                borderRadius: 6,
                fontSize: 12,
              }}
              labelFormatter={(v: number) =>
                `${Math.floor(v / 60)}:${String(v % 60).padStart(2, '0')}`
              }
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={color}
              fill={color}
              fillOpacity={0.15}
              name={label}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
