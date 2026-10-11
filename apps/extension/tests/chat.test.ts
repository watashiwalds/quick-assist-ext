/**
 * X02 — chat RAG phía extension: bộ đọc SSE (mảnh cắt ngang dòng, CRLF, keep-alive), background chuyển
 * tiếp sự kiện qua Port, Dừng → `stopped`, lỗi HTTP / mất kết nối giữa chừng → `error`, lịch sử ≤ 5 cặp.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createSseParser, type SseEvent } from '../src/shared/api/sse'
import { AppError } from '../src/shared/errors'
import type { ChatPortEvent } from '../src/shared/messaging/protocol'
import { installChrome } from './helpers/chrome'

installChrome()
const stream = vi.fn()
vi.mock('../src/background/api', () => ({ http: { stream: (...a: unknown[]) => stream(...a) } }))
const { ask } = await import('../src/background/chat')
const { buildHistory } = await import('../src/ui/features/chat/useChat')

function sse(chunks: string[]): Response {
  const enc = new TextEncoder()
  return new Response(new ReadableStream({
    start(c) {
      for (const ch of chunks) c.enqueue(enc.encode(ch))
      c.close()
    },
  }))
}

describe('createSseParser', () => {
  it('gom sự kiện qua các mảnh bị cắt ngang, hỗ trợ CRLF, bỏ comment', () => {
    const got: SseEvent[] = []
    const p = createSseParser((e) => got.push(e))
    for (const ch of [': ping\r\n\r', '\nevent: so', 'urces\r\ndata: []\r\n', '\r\nevent: delta\ndata: {"text":"a"}\n', '\n', 'data: x'])
      p.feed(ch)
    p.end()
    expect(got).toEqual([
      { event: 'sources', data: '[]' },
      { event: 'delta', data: '{"text":"a"}' },
      { event: 'message', data: 'x' },
    ])
  })

  it('data nhiều dòng được nối bằng \\n', () => {
    const got: SseEvent[] = []
    const p = createSseParser((e) => got.push(e))
    p.feed('event: delta\ndata: a\ndata: b\n\n')
    expect(got).toEqual([{ event: 'delta', data: 'a\nb' }])
  })
})

describe('background ask()', () => {
  const req = { type: 'ask' as const, question: 'phở?', folderId: null, history: [] }
  let events: ChatPortEvent[]
  beforeEach(() => {
    stream.mockReset()
    events = []
  })

  it('chuyển tiếp sources → delta → done, gửi đúng body', async () => {
    stream.mockResolvedValue(sse([
      'event: sources\ndata: [{"index":1,"note_id":"n1","chunk_id":"c1","title":"Phở","url":null,"snippet":"s"}]\n\n',
      'event: delta\ndata: {"text":"Phở bò [1]"}\n\nevent: do',
      'ne\ndata: {"tokens_used": 42}\n\n',
    ]))
    await ask(req, new AbortController().signal, (e) => events.push(e))
    expect(stream.mock.calls[0]![0]).toBe('/ai/chat')
    expect(stream.mock.calls[0]![1].body).toEqual({ question: 'phở?', folder_id: null, history: [] })
    expect(events.map((e) => e.type)).toEqual(['sources', 'delta', 'done'])
    expect(events[1]).toEqual({ type: 'delta', text: 'Phở bò [1]' })
    expect(events[2]).toEqual({ type: 'done', tokensUsed: 42 })
  })

  it('sự kiện error của server → error với mã từ server', async () => {
    stream.mockResolvedValue(sse(['event: sources\ndata: []\n\nevent: error\ndata: {"code":"AI_UNAVAILABLE","message":"x"}\n\n']))
    await ask(req, new AbortController().signal, (e) => events.push(e))
    expect(events.at(-1)).toMatchObject({ type: 'error', error: { code: 'AI_UNAVAILABLE' } })
  })

  it('luồng đứt trước done → NETWORK_ERROR (không treo ở trạng thái đang trả lời)', async () => {
    stream.mockResolvedValue(sse(['event: delta\ndata: {"text":"a"}\n\n']))
    await ask(req, new AbortController().signal, (e) => events.push(e))
    expect(events.at(-1)).toMatchObject({ type: 'error', error: { code: 'NETWORK_ERROR' } })
  })

  it('lỗi HTTP (hết quota) → error giữ nguyên mã', async () => {
    stream.mockRejectedValue(new AppError('QUOTA_EXCEEDED', 'hết', 402))
    await ask(req, new AbortController().signal, (e) => events.push(e))
    expect(events).toEqual([{ type: 'error', error: expect.objectContaining({ code: 'QUOTA_EXCEEDED', status: 402 }) }])
  })

  it('Dừng (abort) → stopped, không báo lỗi', async () => {
    const ctrl = new AbortController()
    stream.mockImplementation(() => {
      ctrl.abort()
      return Promise.reject(new AppError('ABORTED', 'huỷ'))
    })
    await ask(req, ctrl.signal, (e) => events.push(e))
    expect(events).toEqual([{ type: 'stopped' }])
  })
})

describe('buildHistory', () => {
  const pair = (i: number, status = 'done' as const) => [
    { id: `q${i}`, role: 'user' as const, text: `hỏi ${i}` },
    { id: `a${i}`, role: 'assistant' as const, text: `đáp ${i}`, status },
  ]
  it('chỉ giữ 5 cặp hoàn chỉnh gần nhất, bỏ câu trả lời lỗi/rỗng', () => {
    const msgs = [
      ...[0, 1, 2, 3, 4, 5].flatMap((i) => pair(i)),
      { id: 'qx', role: 'user' as const, text: 'lỗi' },
      { id: 'ax', role: 'assistant' as const, text: '', status: 'error' as const },
    ]
    const h = buildHistory(msgs)
    expect(h).toHaveLength(10)
    expect(h[0]).toEqual({ role: 'user', content: 'hỏi 1' })
    expect(h.at(-1)).toEqual({ role: 'assistant', content: 'đáp 5' })
  })
})
