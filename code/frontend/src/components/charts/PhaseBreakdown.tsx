import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { PhaseMetricEntry } from '../../lib/types'

interface Props {
  data: PhaseMetricEntry[]
  fightDurationMs: number
}

export default function PhaseBreakdown({ data, fightDurationMs }: Props) {
  const chartData = data.map((p) => ({
    name: p.phase_name,
    dps: p.phase_dps ?? 0,
    casts: p.phase_casts ?? 0,
    gcd: p.phase_gcd_uptime_pct ?? 0,
    duration: ((p.phase_end_ms - p.phase_start_ms) / 1000).toFixed(0) + 's',
    isDowntime: p.is_downtime,
  }))

  return (
    <div className="space-y-4">
      {/* Phase DPS chart */}
      <div>
        <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-500">
          DPS by Phase
        </h4>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis type="number" stroke="#71717a" tick={{ fontSize: 11 }} />
            <YAxis
              type="category"
              dataKey="name"
              stroke="#71717a"
              width={160}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#18181b',
                border: '1px solid #3f3f46',
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(value: number) => [value.toLocaleString(), 'DPS']}
            />
            <Bar dataKey="dps" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, i) => (
                <Cell
                  key={i}
                  fill={entry.isDowntime ? '#52525b' : '#f59e0b'}
                  fillOpacity={entry.isDowntime ? 0.5 : 0.8}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Phase summary cards */}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {data.map((p) => (
          <div
            key={p.phase_name}
            className={`rounded-lg border p-3 ${
              p.is_downtime
                ? 'border-zinc-700 bg-zinc-800/30'
                : 'border-zinc-700 bg-zinc-900/50'
            }`}
          >
            <div className="flex items-center gap-2">
              <div
                className={`h-2 w-2 rounded-full ${
                  p.is_downtime ? 'bg-zinc-500' : 'bg-amber-400'
                }`}
              />
              <span className="text-sm font-medium text-zinc-200">
                {p.phase_name}
              </span>
              {p.is_downtime && (
                <span className="rounded bg-zinc-700 px-1.5 py-0.5 text-[10px] text-zinc-400">
                  DOWNTIME
                </span>
              )}
            </div>
            <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
              <div>
                <span className="text-zinc-500">DPS</span>
                <p className="font-mono text-zinc-200">
                  {(p.phase_dps ?? 0).toLocaleString()}
                </p>
              </div>
              <div>
                <span className="text-zinc-500">Casts</span>
                <p className="font-mono text-zinc-200">{p.phase_casts ?? 0}</p>
              </div>
              <div>
                <span className="text-zinc-500">GCD</span>
                <p className="font-mono text-zinc-200">
                  {(p.phase_gcd_uptime_pct ?? 0).toFixed(1)}%
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
