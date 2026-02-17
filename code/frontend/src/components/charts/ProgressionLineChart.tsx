import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ProgressionPoint } from '../../lib/types'

interface Props {
  data: ProgressionPoint[]
}

export default function ProgressionLineChart({ data }: Props) {
  const chartData = data.map((p) => ({
    ...p,
    date: new Date(p.time).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  }))

  return (
    <ResponsiveContainer width="100%" height={350}>
      <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis dataKey="date" stroke="#71717a" fontSize={12} />
        <YAxis yAxisId="left" stroke="#71717a" fontSize={12} label={{ value: 'Parse %', angle: -90, position: 'insideLeft', fill: '#71717a' }} />
        <YAxis yAxisId="right" orientation="right" stroke="#71717a" fontSize={12} label={{ value: 'DPS', angle: 90, position: 'insideRight', fill: '#71717a' }} />
        <Tooltip
          contentStyle={{ backgroundColor: '#18181b', border: '1px solid #3f3f46', borderRadius: '8px' }}
          labelStyle={{ color: '#a1a1aa' }}
        />
        <Legend />
        <Line yAxisId="left" type="monotone" dataKey="best_parse" name="Best Parse %" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} />
        <Line yAxisId="left" type="monotone" dataKey="median_parse" name="Median Parse %" stroke="#f97316" strokeWidth={2} dot={{ r: 3 }} />
        <Line yAxisId="right" type="monotone" dataKey="best_dps" name="Best DPS" stroke="#22c55e" strokeWidth={2} dot={{ r: 3 }} />
        <Line yAxisId="right" type="monotone" dataKey="median_dps" name="Median DPS" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}
