import type { ReactNode } from 'react'
import { CheckCircle2, Skull } from 'lucide-react'
import { formatDuration } from '../../lib/wow-classes'

interface Props {
  name: string
  kill: boolean
  durationMs: number
  deaths?: number | null
  avgDps?: number | null
  playerCount?: number
  children?: ReactNode
  onClick?: () => void
}

export default function BossCard({
  name,
  kill,
  durationMs,
  deaths,
  avgDps,
  playerCount,
  children,
  onClick,
}: Props) {
  return (
    <div
      className={`rounded-lg border bg-zinc-900/50 p-4 transition-colors ${
        kill ? 'border-zinc-800' : 'border-red-900/50'
      } ${onClick ? 'cursor-pointer hover:border-zinc-700' : ''}`}
      onClick={onClick}
    >
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold text-zinc-100">{name}</h3>
        {kill ? (
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
        ) : (
          <Skull className="h-5 w-5 text-red-500" />
        )}
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-zinc-500">Time</span>
          <p className="font-mono text-zinc-300">{formatDuration(durationMs)}</p>
        </div>
        {deaths != null && (
          <div>
            <span className="text-zinc-500">Deaths</span>
            <p className={`font-mono ${deaths > 0 ? 'text-red-400' : 'text-zinc-300'}`}>
              {deaths}
            </p>
          </div>
        )}
        {avgDps != null && (
          <div>
            <span className="text-zinc-500">Avg DPS</span>
            <p className="font-mono text-zinc-300">{avgDps.toLocaleString()}</p>
          </div>
        )}
        {playerCount != null && (
          <div>
            <span className="text-zinc-500">Players</span>
            <p className="font-mono text-zinc-300">{playerCount}</p>
          </div>
        )}
      </div>
      {children}
    </div>
  )
}
