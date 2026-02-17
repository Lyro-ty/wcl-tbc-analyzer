import { useEffect, useRef } from 'react'
import { Loader2 } from 'lucide-react'
import type { ChatMessage } from '../../lib/types'
import MessageBubble from './MessageBubble'

interface Props {
  messages: ChatMessage[]
  loading?: boolean
}

export default function MessageList({ messages, loading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  if (messages.length === 0 && !loading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 text-zinc-500">
        <div className="text-6xl">&#9876;</div>
        <h2 className="text-lg font-semibold text-zinc-300">Shukketsu Raid Analyzer</h2>
        <p className="max-w-md text-center text-sm">
          Ask about your raid performance, compare kills to top guilds, track progression,
          or analyze any encounter.
        </p>
        <div className="mt-2 grid gap-2 text-xs">
          <span className="rounded bg-zinc-800 px-3 py-1.5">&quot;How did I do on Patchwerk?&quot;</span>
          <span className="rounded bg-zinc-800 px-3 py-1.5">&quot;Compare our Naxx run to top guilds&quot;</span>
          <span className="rounded bg-zinc-800 px-3 py-1.5">&quot;What spec tops DPS on Thaddius?&quot;</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {loading && (
        <div className="flex justify-start">
          <div className="flex items-center gap-2 rounded-lg bg-zinc-800/50 px-4 py-3 text-sm text-zinc-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            Analyzing...
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
