import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { OverhealSummary } from '../../lib/types'

interface Props {
  data: OverhealSummary
}

export default function OverhealChart({ data }: Props) {
  const chartData = data.abilities.slice(0, 12).map((a) => ({
    name: a.ability_name.length > 20 ? a.ability_name.slice(0, 18) + '…' : a.ability_name,
    effective: a.total,
    overheal: a.overheal_total,
    overhealPct: a.overheal_pct,
  }))

  const totalColor =
    data.total_overheal_pct >= 50
      ? 'text-red-400'
      : data.total_overheal_pct >= 30
        ? 'text-amber-400'
        : 'text-emerald-400'

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-zinc-400">
          Effective: {data.total_effective.toLocaleString()} | Overheal:{' '}
          {data.total_overheal.toLocaleString()}
        </span>
        <span className={`font-bold ${totalColor}`}>
          {data.total_overheal_pct.toFixed(1)}% Overheal
        </span>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={Math.max(chartData.length * 32, 120)}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 10 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={140}
            tick={{ fill: '#a1a1aa', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{
              background: '#18181b',
              border: '1px solid #3f3f46',
              borderRadius: 6,
              fontSize: 12,
            }}
            formatter={(value: number, name: string) => [
              value.toLocaleString(),
              name === 'effective' ? 'Effective' : 'Overheal',
            ]}
          />
          <Bar dataKey="effective" stackId="a" fill="#22c55e" radius={0} />
          <Bar dataKey="overheal" stackId="a" radius={[0, 4, 4, 0]}>
            {chartData.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.overhealPct >= 50 ? '#ef4444' : entry.overhealPct >= 30 ? '#f59e0b' : '#f87171'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
