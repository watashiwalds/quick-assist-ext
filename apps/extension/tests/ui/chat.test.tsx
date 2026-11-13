// @vitest-environment happy-dom
/** X02 — giao diện Hỏi AI: stream từng phần, trích dẫn [n] mở ghi chú, nút Dừng, lỗi hết quota. */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChatSource } from '../../src/shared/api/types'
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

describe('Markdown trong câu trả lời AI', () => {
  const SOURCE: ChatSource = { index: 1, note_id: 'n1', chunk_id: 'c1', title: 'Phở bò', url: null, snippet: 'hầm xương' }

  /** Hỏi rồi đẩy nguyên một câu trả lời (kèm nguồn) vào hội thoại. */
  async function answerWith(text: string, sources: ChatSource[] = []) {
    await ask('hỏi')
    act(() => {
      emit({ type: 'sources', sources })
      emit({ type: 'delta', text })
      emit({ type: 'done', tokensUsed: 1 })
    })
  }

  it('render tiêu đề, chữ đậm, danh sách thay vì cú pháp thô', async () => {
    await answerWith('## Kết luận\n\nNước dùng **rất quan trọng**.\n\n- ý một\n- ý hai')
    expect(screen.getByRole('heading', { name: 'Kết luận' })).toBeTruthy()
    expect(screen.getByText('rất quan trọng').tagName).toBe('STRONG')
    expect(document.querySelectorAll('.ai-text ul li')).toHaveLength(2)
  })

  it('trích dẫn [n] trùng nguồn bấm được; số không có nguồn giữ nguyên chữ', async () => {
    await answerWith('Theo [1] nhưng [9] thì không.', [SOURCE])
    fireEvent.click(screen.getByRole('button', { name: 'Mở ghi chú nguồn 1: Phở bò' }))
    expect(onOpenNote).toHaveBeenCalledWith('n1')
    expect(screen.getByText(/\[9\] thì không/)).toBeTruthy()
  })

  it('code block và inline code giữ nguyên [n]; link javascript: bị gỡ href', async () => {
    await answerWith('Chạy `x [1]` rồi:\n\n```bash\nkubectl get [1]\n```\n\n[bấm](javascript:alert(1))', [SOURCE])
    expect(screen.getByText('kubectl get [1]').closest('pre')).toBeTruthy()
    expect(screen.getByText('x [1]').closest('code')).toBeTruthy()
    const link = screen.getByText('bấm').closest('a')
    expect(link).toBeTruthy()
    expect(link?.getAttribute('href') ?? '').not.toContain('javascript')
    expect(screen.queryByRole('button', { name: 'Mở ghi chú nguồn 1: Phở bò' })).toBeNull()
  })

  it('HTML thô trong câu trả lời không được render thành thẻ', async () => {
    await answerWith('Xin chào <img src=x onerror="window.__pwned = 1"> bạn')
    expect(document.querySelector('.ai-text img')).toBeNull()
  })

  it('bảng GFM render thành bảng thật', async () => {
    await answerWith('| Thứ | Món |\n| --- | --- |\n| 1 | phở |')
    expect(screen.getByRole('table')).toBeTruthy()
  })
})
