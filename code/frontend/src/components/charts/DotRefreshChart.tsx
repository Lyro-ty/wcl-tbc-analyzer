import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { DotRefreshEntry } from '../../lib/types'

interface Props {
  data: DotRefreshEntry[]
}

function refreshColor(earlyPct: number): string {
  if (earlyPct <= 10) return '#22c55e'
  if (earlyPct <= 25) return '#eab308'
  return '#ef4444'
}

function refreshGrade(earlyPct: number): string {
  if (earlyPct <= 10) return 'EXCELLENT'
  if (earlyPct <= 25) return 'OK'
  return 'CLIPPING'
}

export default function DotRefreshChart({ data }: Props) {
  if (data.length === 0) return null

  const chartData = data.map((d) => ({
    name:
      d.ability_name.length > 20 ? d.ability_name.slice(0, 18) + '...' : d.ability_name,
    fullName: d.ability_name,
    earlyPct: d.early_refresh_pct,
    early: d.early_refreshes,
    total: d.total_refreshes,
    clipped: d.clipped_ticks_est,
    avgRemaining: d.avg_remaining_ms,
    fill: refreshColor(d.early_refresh_pct),
  }))

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(120, data.length * 50)}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 4, right: 60, bottom: 4, left: 120 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
          <XAxis
            type="number"
            stroke="#52525b"
            fontSize={11}
            tickFormatter={(v: number) => `${v}%`}
            domain={[0, 100]}
          />
          <YAxis
            type="category"
            dataKey="name"
            stroke="#71717a"
            fontSize={11}
            width={120}
            tick={{ fill: '#a1a1aa' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#18181b',
              border: '1px solid #3f3f46',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            labelStyle={{ color: '#e4e4e7', fontWeight: 600 }}
            formatter={(_val: number, _name: string, props: { payload: typeof chartData[0] }) => {
              const d = props.payload
              return [
                `${d.early}/${d.total} early (${d.earlyPct.toFixed(1)}%) — ~${d.clipped} ticks clipped`,
                d.fullName,
              ]
            }}
          />
          <Bar dataKey="earlyPct" name="Early Refresh %" radius={[0, 4, 4, 0]} barSize={22}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="mt-3 space-y-1">
        {data.map((d) => (
          <div
            key={d.spell_id}
            className="flex items-center gap-3 rounded px-3 py-1.5 text-xs hover:bg-zinc-800/50"
          >
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: refreshColor(d.early_refresh_pct) }}
            />
            <span className="w-32 shrink-0 font-medium text-zinc-200">{d.ability_name}</span>
            <span className="font-mono text-zinc-400">
              {d.early_refreshes}/{d.total_refreshes} early
            </span>
            <span className="font-mono" style={{ color: refreshColor(d.early_refresh_pct) }}>
              {d.early_refresh_pct.toFixed(1)}% — {refreshGrade(d.early_refresh_pct)}
            </span>
            {d.clipped_ticks_est > 0 && (
              <span className="text-red-400/80">~{d.clipped_ticks_est} ticks clipped</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
