/**
 * Trạng thái hội thoại chat RAG (X02). Đặt ở Shell của side panel để chuyển tab không mất hội thoại
 * và câu trả lời đang stream vẫn tiếp tục. Lịch sử chỉ nằm trong bộ nhớ panel (đóng panel = hết) —
 * server không lưu nội dung chat (ADR-0012).
 */
import { useCallback, useRef, useState } from 'react'
import type { ChatSource, ChatTurn } from '@/shared/api/types'
import type { SerializedError } from '@/shared/errors'
import { askChat } from '@/shared/messaging/client'

export const MAX_HISTORY_PAIRS = 5

export interface ChatMessageItem {
  id: string
  role: 'user' | 'assistant'
  text: string
  sources?: ChatSource[]
  status?: 'streaming' | 'done' | 'stopped' | 'error'
  error?: SerializedError
}

/** 5 cặp hỏi–đáp hoàn chỉnh gần nhất (bỏ câu trả lời lỗi/rỗng) để gửi kèm câu hỏi mới. */
export function buildHistory(messages: ChatMessageItem[]): ChatTurn[] {
  const pairs: ChatTurn[][] = []
  for (let i = 0; i + 1 < messages.length; i++) {
    const q = messages[i]!
    const a = messages[i + 1]!
    if (q.role === 'user' && a.role === 'assistant' && a.text.trim() && (a.status === 'done' || a.status === 'stopped')) {
      pairs.push([
        { role: 'user', content: q.text },
        { role: 'assistant', content: a.text },
      ])
    }
  }
  return pairs.slice(-MAX_HISTORY_PAIRS).flat()
}

let seq = 0
const newId = () => `m${Date.now().toString(36)}${(seq++).toString(36)}`

export function useChat() {
  const [messages, setMessages] = useState<ChatMessageItem[]>([])
  const [folderId, setFolderId] = useState<string | null>(null)
  const stopRef = useRef<(() => void) | null>(null)
  const streaming = messages.some((m) => m.status === 'streaming')

  const patch = useCallback((id: string, fn: (m: ChatMessageItem) => ChatMessageItem) => {
    setMessages((ms) => ms.map((m) => (m.id === id ? fn(m) : m)))
  }, [])

  const msgsRef = useRef(messages)
  msgsRef.current = messages

  const ask = useCallback(
    (question: string) => {
      const q = question.trim()
      if (!q || stopRef.current) return
      const history = buildHistory(msgsRef.current)
      const answerId = newId()
      setMessages((ms) => [
        ...ms,
        { id: newId(), role: 'user', text: q },
        { id: answerId, role: 'assistant', text: '', status: 'streaming' },
      ])
      const { stop } = askChat({ question: q, folderId, history }, (e) => {
        if (e.type === 'sources') patch(answerId, (m) => ({ ...m, sources: e.sources }))
        else if (e.type === 'delta') patch(answerId, (m) => ({ ...m, text: m.text + e.text }))
        else {
          stopRef.current = null
          if (e.type === 'done') patch(answerId, (m) => ({ ...m, status: 'done' }))
          else if (e.type === 'stopped') patch(answerId, (m) => ({ ...m, status: 'stopped' }))
          else patch(answerId, (m) => ({ ...m, status: 'error', error: e.error }))
        }
      })
      stopRef.current = stop
    },
    [folderId, patch],
  )

  const stop = useCallback(() => stopRef.current?.(), [])

  const reset = useCallback(() => {
    stopRef.current?.()
    stopRef.current = null
    setMessages([])
  }, [])

  return { messages, streaming, folderId, setFolderId, ask, stop, reset }
}

export type ChatState = ReturnType<typeof useChat>
