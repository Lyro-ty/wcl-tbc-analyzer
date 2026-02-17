import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { SpeedComparison } from '../../lib/types'

interface Props {
  data: SpeedComparison[]
}

export default function SpeedComparisonChart({ data }: Props) {
  const chartData = data.map((d) => ({
    name: d.encounter_name,
    yours: Math.round(d.duration_ms / 1000),
    wr: d.world_record_ms ? Math.round(d.world_record_ms / 1000) : null,
    top10: d.top10_avg_ms ? Math.round(d.top10_avg_ms / 1000) : null,
    top100: d.top100_median_ms ? Math.round(d.top100_median_ms / 1000) : null,
  }))

  return (
    <ResponsiveContainer width="100%" height={Math.max(300, data.length * 60)}>
      <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 80 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
        <XAxis type="number" stroke="#71717a" fontSize={12} label={{ value: 'Seconds', position: 'insideBottom', fill: '#71717a' }} />
        <YAxis type="category" dataKey="name" stroke="#71717a" fontSize={12} width={80} />
        <Tooltip
          contentStyle={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', borderRadius: '8px' }}
          labelStyle={{ color: '#a1a1aa' }}
          formatter={(val: number) => `${Math.floor(val / 60)}m ${val % 60}s`}
        />
        <Legend />
        <Bar dataKey="yours" name="Your Time" fill="#ef4444" radius={[0, 4, 4, 0]} />
        <Bar dataKey="top10" name="Top 10 Avg" fill="#3b82f6" radius={[0, 4, 4, 0]} />
        <Bar dataKey="top100" name="Top 100 Median" fill="#6b7280" radius={[0, 4, 4, 0]} />
        {chartData.some((d) => d.wr) && (
          <ReferenceLine x={0} stroke="transparent" />
        )}
      </BarChart>
    </ResponsiveContainer>
  )
}
