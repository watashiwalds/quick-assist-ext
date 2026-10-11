/**
 * Chat RAG ở background (X02, ADR-0009): mỗi câu hỏi = một Port `qa-chat` từ side panel.
 * Gọi POST /ai/chat (SSE) bằng token của background, chuyển tiếp từng sự kiện về Port.
 * `stop` hoặc Port bị đóng (đóng panel) → AbortController.abort() → server dừng sinh, chỉ trừ phần đã sinh.
 */
import type { ChatSource } from '@/shared/api/types'
import { createSseParser } from '@/shared/api/sse'
import { AppError } from '@/shared/errors'
import type { ChatClientMessage, ChatPortEvent } from '@/shared/messaging/protocol'
import { http } from './api'

export function handleChatPort(port: chrome.runtime.Port): void {
  let ctrl: AbortController | null = null
  let closed = false
  const post = (e: ChatPortEvent) => {
    if (closed) return
    try {
      port.postMessage(e)
    } catch {
      closed = true
    }
  }

  port.onDisconnect.addListener(() => {
    closed = true
    ctrl?.abort()
  })
  port.onMessage.addListener((msg: ChatClientMessage) => {
    if (msg.type === 'stop') {
      ctrl?.abort()
      return
    }
    if (msg.type === 'ask') {
      ctrl?.abort()
      const mine = new AbortController()
      ctrl = mine
      void ask(msg, mine.signal, post)
    }
  })
}

export async function ask(
  msg: Extract<ChatClientMessage, { type: 'ask' }>,
  signal: AbortSignal,
  post: (e: ChatPortEvent) => void,
): Promise<void> {
  let ended = false
  const parser = createSseParser(({ event, data }) => {
    if (ended) return
    try {
      const d = JSON.parse(data) as Record<string, unknown>
      if (event === 'sources') post({ type: 'sources', sources: d as unknown as ChatSource[] })
      else if (event === 'delta') post({ type: 'delta', text: String(d.text ?? '') })
      else if (event === 'done') {
        ended = true
        post({ type: 'done', tokensUsed: Number(d.tokens_used ?? 0) })
      } else if (event === 'error') {
        ended = true
        post({ type: 'error', error: new AppError(String(d.code ?? 'AI_UNAVAILABLE'), String(d.message ?? ''), 502).toJSON() })
      }
    } catch {
      /* sự kiện hỏng → bỏ qua */
    }
  })
  try {
    const res = await http.stream('/ai/chat', {
      method: 'POST',
      body: { question: msg.question, folder_id: msg.folderId ?? null, history: msg.history },
      signal,
    })
    const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader()
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      parser.feed(value)
    }
    parser.end()
    if (!ended) post({ type: 'error', error: new AppError('NETWORK_ERROR', 'Mất kết nối giữa chừng').toJSON() })
  } catch (e) {
    if (ended) return
    if (signal.aborted) return post({ type: 'stopped' })
    const err = e instanceof AppError ? e : new AppError('NETWORK_ERROR', String(e))
    post({ type: 'error', error: err.toJSON() })
  }
}
