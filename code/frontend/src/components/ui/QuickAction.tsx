import { MessageSquare } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export default function QuickAction({ question }: { question: string }) {
  const navigate = useNavigate()

  return (
    <button
      onClick={() => navigate(`/?q=${encodeURIComponent(question)}`)}
      className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800/50 px-2.5 py-1 text-xs text-zinc-300 transition-colors hover:border-zinc-600 hover:bg-zinc-800 hover:text-zinc-100"
      title="Ask the agent"
    >
      <MessageSquare className="h-3.5 w-3.5" />
      Ask Agent
    </button>
  )
}
