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
import type { CooldownWindowEntry } from '../../lib/types'
import { formatDuration } from '../../lib/wow-classes'

interface Props {
  data: CooldownWindowEntry[]
  fightDurationMs: number
}

function gainColor(pct: number): string {
  if (pct >= 50) return '#22c55e'
  if (pct >= 20) return '#84cc16'
  if (pct >= 0) return '#eab308'
  return '#ef4444'
}

export default function CooldownWindowChart({ data, fightDurationMs }: Props) {
  if (data.length === 0) return null

  const chartData = data.map((d) => ({
    name:
      d.ability_name.length > 18 ? d.ability_name.slice(0, 16) + '...' : d.ability_name,
    fullName: d.ability_name,
    windowDps: Math.round(d.window_dps),
    baselineDps: Math.round(d.baseline_dps),
    gainPct: d.dps_gain_pct,
    startMs: d.window_start_ms,
    endMs: d.window_end_ms,
    fill: gainColor(d.dps_gain_pct),
  }))

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 50)}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 4, right: 60, bottom: 4, left: 120 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
          <XAxis type="number" stroke="#52525b" fontSize={11} />
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
            formatter={(_val: number, name: string, props: { payload: typeof chartData[0] }) => {
              const d = props.payload
              if (name === 'Baseline') return [`${d.baselineDps.toLocaleString()} DPS`, 'Baseline']
              return [
                `${d.windowDps.toLocaleString()} DPS (+${d.gainPct.toFixed(1)}%)`,
                d.fullName,
              ]
            }}
          />
          <Bar dataKey="baselineDps" name="Baseline" fill="#3f3f46" radius={[0, 4, 4, 0]} barSize={16} />
          <Bar dataKey="windowDps" name="During CD" radius={[0, 4, 4, 0]} barSize={16}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="mt-3 space-y-1">
        {data.map((d, i) => (
          <div
            key={i}
            className="flex items-center gap-3 rounded px-3 py-1.5 text-xs hover:bg-zinc-800/50"
          >
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: gainColor(d.dps_gain_pct) }}
            />
            <span className="w-28 shrink-0 font-medium text-zinc-200">{d.ability_name}</span>
            <span className="font-mono text-zinc-400">
              {Math.round(d.window_dps).toLocaleString()} vs {Math.round(d.baseline_dps).toLocaleString()} DPS
            </span>
            <span className="font-mono" style={{ color: gainColor(d.dps_gain_pct) }}>
              +{d.dps_gain_pct.toFixed(1)}%
            </span>
            <span className="text-zinc-500">
              @ {formatDuration(d.window_start_ms)}{fightDurationMs > 0 ? `–${formatDuration(d.window_end_ms)}` : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
