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
    expect(onOpenNote).toHaveBeenCalledTimes(1)

    // Chip nguồn và trích dẫn [1] là hai lối mở cùng một ghi chú.
    fireEvent.click(screen.getByRole('button', { name: 'Mở ghi chú nguồn 1: Phở bò' }))
    expect(onOpenNote).toHaveBeenCalledTimes(2)
  })

  it('nút Dừng gọi stop; trả lời bị dừng vẫn giữ phần đã sinh', async () => {
    await ask('hỏi')
    act(() => emit({ type: 'delta', text: 'một phần' }))
    fireEvent.click(screen.getByRole('button', { name: 'Dừng' }))
    expect(stop).toHaveBeenCalled()
    act(() => emit({ type: 'stopped' }))
    expect(screen.getByText('một phần')).toBeTruthy()
    expect(screen.getByText('Đã dừng')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Hỏi lại' })).toBeTruthy()
  })

  it('nhãn Nguồn (n) + chi tiết nguồn chỉ mở sau khi trả lời xong', async () => {
    await ask('phở?')
    act(() => {
      emit({ type: 'sources', sources: [{ index: 1, note_id: 'n1', chunk_id: 'c1', title: 'Phở bò', url: null, snippet: 'hầm xương 8 tiếng' }] })
      emit({ type: 'delta', text: 'Nội dung [1]' })
    })
    expect(screen.getByText('Nguồn (1)')).toBeTruthy()
    expect(screen.getByText(/chi tiết mở khi câu trả lời hoàn tất/)).toBeTruthy()
    expect(screen.queryByText('Chi tiết nguồn')).toBeNull()

    act(() => emit({ type: 'done', tokensUsed: 3 }))
    expect(screen.getByText('Chi tiết nguồn')).toBeTruthy()
    expect(screen.getByText('hầm xương 8 tiếng')).toBeTruthy()
  })

  it('sao chép câu trả lời vào clipboard', async () => {
    const original = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    try {
      await ask('hỏi')
      act(() => {
        emit({ type: 'delta', text: 'đáp án' })
        emit({ type: 'done', tokensUsed: 1 })
      })
      fireEvent.click(screen.getByRole('button', { name: 'Sao chép câu trả lời' }))
      await waitFor(() => expect(writeText).toHaveBeenCalledWith('đáp án'))
    } finally {
      if (original) Object.defineProperty(navigator, 'clipboard', original)
      else Reflect.deleteProperty(navigator, 'clipboard')
    }
  })

  it('trạng thái trống gợi ý câu hỏi mẫu và gửi ngay khi bấm', async () => {
    render(<Harness />)
    expect(screen.getByRole('heading', { name: 'Hỏi AI về ghi chú của bạn' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Tóm tắt những gì mình đã lưu tuần này' }))
    await waitFor(() => expect(askChat).toHaveBeenCalled())
    expect(askChat.mock.calls[0]![0]).toMatchObject({ question: 'Tóm tắt những gì mình đã lưu tuần này' })
  })

  it('không gọi lặp RPC dung lượng khi không truyền phiên (deps ổn định)', async () => {
    render(<Harness />)
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('chatSessions/usage'))
    const input = screen.getByLabelText('Câu hỏi về ghi chú')
    fireEvent.change(input, { target: { value: 'a' } })
    fireEvent.change(input, { target: { value: 'ab' } })
    await act(async () => {
      await Promise.resolve()
    })
    expect(rpc.mock.calls.filter((c) => c[0] === 'chatSessions/usage')).toHaveLength(1)
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
