import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { CooldownUsageEntry } from '../../lib/types'

interface Props {
  data: CooldownUsageEntry[]
}

function efficiencyColor(pct: number): string {
  if (pct >= 90) return '#22c55e'
  if (pct >= 70) return '#eab308'
  return '#ef4444'
}

function efficiencyLabel(pct: number): string {
  if (pct >= 90) return 'GOOD'
  if (pct >= 70) return 'OK'
  return 'LOW'
}

export default function CooldownChart({ data }: Props) {
  if (data.length === 0) return null

  const chartData = data.map((d) => ({
    name: d.ability_name.length > 20 ? d.ability_name.slice(0, 18) + '...' : d.ability_name,
    fullName: d.ability_name,
    efficiency: d.efficiency_pct,
    used: d.times_used,
    max: d.max_possible_uses,
    cdSec: d.cooldown_sec,
    fill: efficiencyColor(d.efficiency_pct),
    label: efficiencyLabel(d.efficiency_pct),
  }))

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(140, data.length * 40)}>
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
                `${d.used}/${d.max} uses (${d.efficiency.toFixed(1)}%) [${d.label}] — ${d.cdSec}s CD`,
                d.fullName,
              ]
            }}
          />
          <ReferenceLine x={90} stroke="#22c55e" strokeDasharray="3 3" strokeOpacity={0.4} />
          <ReferenceLine x={70} stroke="#eab308" strokeDasharray="3 3" strokeOpacity={0.3} />
          <Bar dataKey="efficiency" name="Efficiency" radius={[0, 4, 4, 0]} barSize={22}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Detail table below chart */}
      <div className="mt-3 space-y-1">
        {data.map((d) => (
          <div
            key={d.spell_id}
            className="flex items-center gap-3 rounded px-3 py-1.5 text-xs hover:bg-zinc-800/50"
          >
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: efficiencyColor(d.efficiency_pct) }}
            />
            <span className="w-32 shrink-0 font-medium text-zinc-200">{d.ability_name}</span>
            <span className="font-mono text-zinc-400">
              {d.times_used}/{d.max_possible_uses} uses
            </span>
            <span className="font-mono" style={{ color: efficiencyColor(d.efficiency_pct) }}>
              {d.efficiency_pct.toFixed(1)}%
            </span>
            <span className="text-zinc-500">{d.cooldown_sec}s CD</span>
            {d.first_use_ms != null && (
              <span className="text-zinc-500">
                first use: {(d.first_use_ms / 1000).toFixed(1)}s
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
