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
import type { AbilityMetric } from '../../lib/types'

interface Props {
  data: AbilityMetric[]
  accentColor?: string
}

const ABILITY_COLORS = [
  '#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4',
  '#3b82f6', '#8b5cf6', '#d946ef', '#f43f5e', '#14b8a6',
]

export default function AbilityBarChart({ data, accentColor }: Props) {
  const chartData = data.map((d, i) => ({
    name: d.ability_name.length > 20 ? d.ability_name.slice(0, 18) + '...' : d.ability_name,
    fullName: d.ability_name,
    pct: d.pct_of_total,
    total: d.total,
    critPct: d.crit_pct,
    fill: accentColor ?? ABILITY_COLORS[i % ABILITY_COLORS.length],
  }))

  return (
    <ResponsiveContainer width="100%" height={Math.max(200, data.length * 32)}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 4, right: 40, bottom: 4, left: 130 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
        <XAxis
          type="number"
          stroke="#52525b"
          fontSize={11}
          tickFormatter={(v: number) => `${v}%`}
          domain={[0, 'auto']}
        />
        <YAxis
          type="category"
          dataKey="name"
          stroke="#71717a"
          fontSize={11}
          width={130}
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
            if (name === 'pct') {
              return [`${d.pct.toFixed(1)}% of total | ${d.total.toLocaleString()} total | ${d.critPct.toFixed(1)}% crit`, d.fullName]
            }
            return [_val, name]
          }}
        />
        <Bar dataKey="pct" name="pct" radius={[0, 3, 3, 0]} barSize={20}>
          {chartData.map((entry, i) => (
            <Cell key={i} fill={entry.fill} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
