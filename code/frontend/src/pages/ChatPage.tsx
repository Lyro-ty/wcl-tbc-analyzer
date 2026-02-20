import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { postAnalyzeStream } from '../lib/api'
import type { ChatMessage } from '../lib/types'
import ChatInput from '../components/chat/ChatInput'
import MessageList from '../components/chat/MessageList'

function generateId(): string {
  try {
    return crypto.randomUUID()
  } catch {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  }
}

const MAX_MESSAGES = 200

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    (question: string) => {
      const userMsg: ChatMessage = {
        id: generateId(),
        role: 'user',
        content: question,
        timestamp: Date.now(),
      }
      const assistantId = generateId()
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, userMsg, assistantMsg].slice(-MAX_MESSAGES))
      setStreaming(true)

      abortRef.current = postAnalyzeStream(
        question,
        (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token } : m,
            ),
          )
        },
        () => {
          setStreaming(false)
        },
        (error) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content || `Error: ${error}` }
                : m,
            ),
          )
          setStreaming(false)
        },
      )
    },
    [],
  )

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    const q = searchParams.get('q')
    if (q) {
      setSearchParams({}, { replace: true })
      sendMessage(q)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-1 min-h-0 flex-col -m-6">
      <MessageList messages={messages} streaming={streaming} />
      <ChatInput onSend={sendMessage} disabled={streaming} />
    </div>
  )
}
