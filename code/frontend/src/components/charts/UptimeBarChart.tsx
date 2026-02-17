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
import type { BuffUptime } from '../../lib/types'

interface Props {
  data: BuffUptime[]
  label?: string
}

function uptimeColor(pct: number): string {
  if (pct >= 90) return '#22c55e'
  if (pct >= 50) return '#eab308'
  return '#ef4444'
}

function uptimeTier(pct: number): string {
  if (pct >= 90) return 'HIGH'
  if (pct >= 50) return 'MED'
  return 'LOW'
}

export default function UptimeBarChart({ data, label }: Props) {
  const chartData = data.map((d) => ({
    name: d.ability_name.length > 22 ? d.ability_name.slice(0, 20) + '...' : d.ability_name,
    fullName: d.ability_name,
    uptime: Math.min(d.uptime_pct, 100),
    fill: uptimeColor(d.uptime_pct),
    tier: uptimeTier(d.uptime_pct),
  }))

  return (
    <div>
      {label && (
        <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-500">
          {label}
        </p>
      )}
      <ResponsiveContainer width="100%" height={Math.max(180, data.length * 28)}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 4, right: 40, bottom: 4, left: 140 }}
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
            width={140}
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
              return [`${d.uptime.toFixed(1)}% uptime [${d.tier}]`, d.fullName]
            }}
          />
          <ReferenceLine x={90} stroke="#22c55e" strokeDasharray="3 3" strokeOpacity={0.4} />
          <ReferenceLine x={50} stroke="#eab308" strokeDasharray="3 3" strokeOpacity={0.3} />
          <Bar dataKey="uptime" name="Uptime" radius={[0, 3, 3, 0]} barSize={18}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
