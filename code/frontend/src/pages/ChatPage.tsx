import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { postAnalyze } from '../lib/api'
import type { ChatMessage } from '../lib/types'
import ChatInput from '../components/chat/ChatInput'
import MessageList from '../components/chat/MessageList'

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()

  const sendMessage = useCallback(
    async (question: string) => {
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: question,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, userMsg])
      setLoading(true)

      try {
        const res = await postAnalyze(question)
        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: res.answer,
          queryType: res.query_type,
          timestamp: Date.now(),
        }
        setMessages((prev) => [...prev, assistantMsg])
      } catch (err) {
        const errorMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `Error: ${err instanceof Error ? err.message : 'Something went wrong'}`,
          timestamp: Date.now(),
        }
        setMessages((prev) => [...prev, errorMsg])
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    const q = searchParams.get('q')
    if (q) {
      setSearchParams({}, { replace: true })
      sendMessage(q)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex h-full flex-col -m-6">
      <MessageList messages={messages} loading={loading} />
      <ChatInput onSend={sendMessage} disabled={loading} />
    </div>
  )
}
