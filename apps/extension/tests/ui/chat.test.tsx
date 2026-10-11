// @vitest-environment happy-dom
/** X02 — giao diện Hỏi AI: stream từng phần, trích dẫn [n] mở ghi chú, nút Dừng, lỗi hết quota. */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChatPortEvent } from '../../src/shared/messaging/protocol'
import { installChrome } from '../helpers/chrome'

installChrome()
const rpc = vi.fn()
const stop = vi.fn()
let emit: (e: ChatPortEvent) => void = () => undefined
const askChat = vi.fn((_req: unknown, onEvent: (e: ChatPortEvent) => void) => {
  emit = onEvent
  return { stop }
})
vi.mock('../../src/shared/messaging/client', () => ({
  rpc: (...a: unknown[]) => rpc(...a),
  onBroadcast: () => () => undefined,
  askChat: (req: unknown, cb: (e: ChatPortEvent) => void) => askChat(req, cb),
}))

const { ChatView } = await import('../../src/ui/features/chat/ChatView')
const { useChat } = await import('../../src/ui/features/chat/useChat')

const onOpenNote = vi.fn()
function Harness() {
  const chat = useChat()
  return <ChatView chat={chat} onOpenNote={onOpenNote} onGoSettings={() => undefined} />
}

beforeEach(() => {
  rpc.mockReset()
  rpc.mockResolvedValue([])
  askChat.mockClear()
  stop.mockReset()
  onOpenNote.mockReset()
})
afterEach(cleanup)

async function ask(text: string) {
  render(<Harness />)
  fireEvent.change(screen.getByLabelText('Câu hỏi về ghi chú'), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Gửi' }))
  await waitFor(() => expect(askChat).toHaveBeenCalled())
}

describe('ChatView', () => {
  it('hiện câu trả lời dần, trích dẫn bấm được để mở ghi chú nguồn', async () => {
    await ask('cách nấu phở?')
    expect(askChat.mock.calls[0]![0]).toEqual({ question: 'cách nấu phở?', folderId: null, history: [] })
    expect(screen.getByRole('button', { name: 'Dừng' })).toBeTruthy()
    act(() => {
      emit({ type: 'sources', sources: [{ index: 1, note_id: 'n1', chunk_id: 'c1', title: 'Phở bò', url: null, snippet: 'hầm xương' }] })
      emit({ type: 'delta', text: 'Hầm xương 8 tiếng ' })
      emit({ type: 'delta', text: '[1].' })
    })
    expect(screen.getByText(/Hầm xương 8 tiếng/)).toBeTruthy()
    act(() => emit({ type: 'done', tokensUsed: 10 }))
    expect(screen.getByRole('button', { name: 'Gửi' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Nguồn 1: Phở bò' }))
    expect(onOpenNote).toHaveBeenCalledWith('n1')
  })

  it('nút Dừng gọi stop; trả lời bị dừng vẫn giữ phần đã sinh', async () => {
    await ask('hỏi')
    act(() => emit({ type: 'delta', text: 'một phần' }))
    fireEvent.click(screen.getByRole('button', { name: 'Dừng' }))
    expect(stop).toHaveBeenCalled()
    act(() => emit({ type: 'stopped' }))
    expect(screen.getByText('một phần')).toBeTruthy()
    expect(screen.getByText('(đã dừng)')).toBeTruthy()
  })

  it('câu hỏi tiếp theo gửi kèm lịch sử', async () => {
    await ask('câu 1')
    act(() => {
      emit({ type: 'delta', text: 'đáp 1' })
      emit({ type: 'done', tokensUsed: 1 })
    })
    fireEvent.change(screen.getByLabelText('Câu hỏi về ghi chú'), { target: { value: 'câu 2' } })
    fireEvent.keyDown(screen.getByLabelText('Câu hỏi về ghi chú'), { key: 'Enter' })
    await waitFor(() => expect(askChat).toHaveBeenCalledTimes(2))
    expect(askChat.mock.calls[1]![0]).toMatchObject({
      question: 'câu 2',
      history: [{ role: 'user', content: 'câu 1' }, { role: 'assistant', content: 'đáp 1' }],
    })
  })

  it('hết quota → thông báo + lối tắt xem hạn mức', async () => {
    await ask('hỏi')
    act(() => emit({ type: 'error', error: { code: 'QUOTA_EXCEEDED', message: 'x', status: 402 } }))
    expect(screen.getByRole('alert').textContent).toContain('hết hạn mức')
    expect(screen.getByRole('button', { name: 'Xem hạn mức' })).toBeTruthy()
  })
})
