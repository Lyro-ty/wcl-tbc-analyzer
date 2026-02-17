import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { SpecLeaderboardEntry } from '../../lib/types'
import { classColor } from '../../lib/wow-classes'

interface Props {
  data: SpecLeaderboardEntry[]
}

export default function DpsBarChart({ data }: Props) {
  const chartData = data.map((d) => ({
    name: `${d.player_spec} ${d.player_class}`,
    avg_dps: d.avg_dps,
    max_dps: d.max_dps,
    fill: classColor(d.player_class),
  }))

  return (
    <ResponsiveContainer width="100%" height={Math.max(300, data.length * 40)}>
      <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 120 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
        <XAxis type="number" stroke="#71717a" fontSize={12} />
        <YAxis type="category" dataKey="name" stroke="#71717a" fontSize={11} width={120} />
        <Tooltip
          contentStyle={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', borderRadius: '8px' }}
          labelStyle={{ color: '#a1a1aa' }}
          formatter={(val: number) => val.toLocaleString(undefined, { maximumFractionDigits: 1 })}
        />
        <Bar dataKey="avg_dps" name="Avg DPS" radius={[0, 4, 4, 0]}>
          {chartData.map((entry, i) => (
            <rect key={i} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
