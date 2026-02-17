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
  Mana: '#3b82f6',
  Rage: '#ef4444',
  Energy: '#eab308',
}

interface Sample {
  ts: number
  value: number
}

export default function ResourceChart({ data }: Props) {
  const color = RESOURCE_COLORS[data.resource_type] ?? '#a855f7'

  let samples: Sample[] = []
  if (data.samples_json) {
    try {
      samples = JSON.parse(data.samples_json)
    } catch {
      // ignore
    }
  }

  const chartData = samples.map((s) => ({
    time: Math.round(s.ts / 1000),
    value: s.value,
  }))

  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <span
          className="h-3 w-3 rounded-full"
          style={{ backgroundColor: color }}
        />
        <span className="text-sm font-medium text-zinc-200">{data.resource_type}</span>
      </div>

      {/* Stats row */}
      <div className="mb-3 flex gap-6 text-xs">
        <div>
          <span className="text-zinc-500">Min</span>
          <p className="font-mono text-zinc-300">{data.min_value.toLocaleString()}</p>
        </div>
        <div>
          <span className="text-zinc-500">Avg</span>
          <p className="font-mono text-zinc-300">{Math.round(data.avg_value).toLocaleString()}</p>
        </div>
        <div>
          <span className="text-zinc-500">Max</span>
          <p className="font-mono text-zinc-300">{data.max_value.toLocaleString()}</p>
        </div>
        <div>
          <span className="text-zinc-500">Time at 0</span>
          <p className={`font-mono ${data.time_at_zero_pct > 10 ? 'text-red-400' : 'text-zinc-300'}`}>
            {data.time_at_zero_pct.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Line chart */}
      {chartData.length > 2 && (
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis
              dataKey="time"
              stroke="#52525b"
              fontSize={10}
              tickFormatter={(v: number) => `${v}s`}
            />
            <YAxis stroke="#52525b" fontSize={10} width={40} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#18181b',
                border: '1px solid #3f3f46',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              labelFormatter={(v: number) => `${v}s`}
              formatter={(v: number) => [v.toLocaleString(), data.resource_type]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={color}
              fill={color}
              fillOpacity={0.15}
              strokeWidth={1.5}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
