// @vitest-environment happy-dom
/** X02 — giao diện Hỏi AI: stream từng phần, trích dẫn [n] mở ghi chú, nút Dừng, lỗi hết quota. */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
      emit({ type: 'sources', sources: [{ index: 1, source_index: 1, source_domain: null, note_id: 'n1', chunk_id: 'c1', title: 'Phở bò', url: null, snippet: 'hầm xương' }] })
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
      emit({ type: 'sources', sources: [{ index: 1, source_index: 1, source_domain: null, note_id: 'n1', chunk_id: 'c1', title: 'Phở bò', url: null, snippet: 'hầm xương 8 tiếng' }] })
      emit({ type: 'delta', text: 'Nội dung [1]' })
    })
    expect(screen.getByText('Nguồn (1)')).toBeTruthy()
    expect(screen.getByText(/chi tiết mở khi câu trả lời hoàn tất/)).toBeTruthy()
    expect(screen.queryByText('Chi tiết nguồn')).toBeNull()

    act(() => emit({ type: 'done', tokensUsed: 3 }))
    expect(screen.getByText('Chi tiết nguồn')).toBeTruthy()
    expect(screen.getByText('hầm xương 8 tiếng')).toBeTruthy()
  })

  it('chip nguồn nhóm theo domain; "Nguồn (N)" đếm số domain; "Không rõ nguồn" xếp cuối', async () => {
    await ask('phở?')
    act(() => {
      emit({
        type: 'sources',
        sources: [
          { index: 1, source_index: 1, source_domain: 'amthuc.example', note_id: 'n1', chunk_id: 'c1', title: 'Phở bò', url: null, snippet: 'hầm xương' },
          { index: 2, source_index: 1, source_domain: 'amthuc.example', note_id: 'n2', chunk_id: 'c2', title: 'Bún bò', url: null, snippet: 'sả hành' },
          { index: 3, source_index: 2, source_domain: 'wiki.example', note_id: 'n3', chunk_id: 'c3', title: 'Bò', url: null, snippet: 'giống bò' },
          { index: 4, source_index: 3, source_domain: null, note_id: 'n4', chunk_id: 'c4', title: 'Ghi chú tay', url: null, snippet: 'mẹo vặt' },
        ],
      })
      emit({ type: 'done', tokensUsed: 1 })
    })
    // 4 note thuộc 3 domain → nhãn đếm theo domain, không phải số chip.
    expect(screen.getByText('Nguồn (3)')).toBeTruthy()
    const labels = [...document.querySelectorAll('.source-cluster-label')].map((el) => el.textContent)
    expect(labels).toEqual(['amthuc.example', 'wiki.example', 'Không rõ nguồn'])
    // Mỗi note đúng một chip, thuộc đúng nhóm của mình (không trùng giữa các nhóm).
    const chips = [...document.querySelectorAll('.source-chip')]
    expect(chips).toHaveLength(4)
    expect(new Set(chips.map((c) => c.getAttribute('aria-label')))).toHaveLength(4)
  })

  it('trích dẫn [n] và chi tiết nguồn nhóm đúng: bấm mở đúng ghi chú trong nhóm', async () => {
    await ask('bò?')
    act(() => {
      emit({
        type: 'sources',
        sources: [
          { index: 1, source_index: 1, source_domain: 'amthuc.example', note_id: 'n1', chunk_id: 'c1', title: 'Phở bò', url: null, snippet: 'hầm xương' },
          { index: 2, source_index: 2, source_domain: 'wiki.example', note_id: 'n2', chunk_id: 'c2', title: 'Bò', url: null, snippet: 'giống bò' },
          { index: 3, source_index: 3, source_domain: null, note_id: 'n3', chunk_id: 'c3', title: 'Ghi chú tay', url: null, snippet: 'mẹo vặt' },
        ],
      })
      emit({ type: 'delta', text: 'Xem [2].' })
      emit({ type: 'done', tokensUsed: 1 })
    })
    // Trích dẫn [2] trong câu trả lời mở đúng note của nhóm wiki.example.
    fireEvent.click(screen.getByRole('button', { name: 'Mở ghi chú nguồn 2: Bò' }))
    expect(onOpenNote).toHaveBeenCalledWith('n2')

    fireEvent.click(screen.getByText('Chi tiết nguồn'))
    const blocks = [...document.querySelectorAll('.source-group-block')]
    expect(blocks).toHaveLength(3)
    expect([...document.querySelectorAll('.source-domain-name')].map((el) => el.textContent)).toEqual([
      'amthuc.example',
      'wiki.example',
      'Không rõ nguồn',
    ])
    expect([...document.querySelectorAll('.source-domain-count')].map((el) => el.textContent)).toEqual([
      '1 ghi chú',
      '1 ghi chú',
      '1 ghi chú',
    ])
    // "Mở ghi chú" trong khối wiki.example là note n2, không lẫn note nhóm khác.
    fireEvent.click(within(blocks[1] as HTMLElement).getByRole('button', { name: 'Mở ghi chú' }))
    expect(onOpenNote).toHaveBeenCalledWith('n2')
    expect(onOpenNote).toHaveBeenCalledTimes(2)
  })

  it('ADR-0018: chi tiết nguồn tách nhóm con theo trang khi cùng domain có URL khác nhau', async () => {
    await ask('phở?')
    act(() => {
      emit({
        type: 'sources',
        sources: [
          { index: 1, source_index: 1, source_domain: 'amthuc.example', note_id: 'n1', chunk_id: 'c1', title: 'Phở bò', url: 'https://amthuc.example/pho', snippet: 'hầm xương' },
          { index: 2, source_index: 1, source_domain: 'amthuc.example', note_id: 'n2', chunk_id: 'c2', title: 'Bún bò', url: 'https://amthuc.example/bun-bo', snippet: 'sả hành' },
          { index: 3, source_index: 1, source_domain: 'amthuc.example', note_id: 'n1', chunk_id: 'c3', title: 'Phở bò', url: 'https://amthuc.example/pho?utm=x', snippet: 'phần khác' },
        ],
      })
      emit({ type: 'done', tokensUsed: 1 })
    })
    // Chip vẫn gọn theo domain, không dính nhãn trang (D8).
    expect(screen.getByText('Nguồn (1)')).toBeTruthy()
    fireEvent.click(screen.getByText('Chi tiết nguồn'))
    // Domain head đếm thêm số trang.
    expect(screen.getByText('2 ghi chú · 2 trang')).toBeTruthy()
    const pageA = screen.getByRole('region', { name: 'Trang amthuc.example/pho' })
    expect(within(pageA).getAllByText('Phở bò').length).toBe(2) // url chỉ khác query → cùng trang
    expect(within(screen.getByRole('region', { name: 'Trang amthuc.example/bun-bo' })).getByText('Bún bò')).toBeTruthy()
  })

  it('đếm ghi chú của nhóm theo note khác nhau (chip cũ nhiều chunk/note không phình số)', async () => {
    await ask('phở?')
    act(() => {
      emit({
        type: 'sources',
        sources: [
          { index: 1, source_index: 1, source_domain: 'amthuc.example', note_id: 'n1', chunk_id: 'c1', title: 'Phở bò', url: null, snippet: 'phần 1' },
          { index: 2, source_index: 1, source_domain: 'amthuc.example', note_id: 'n1', chunk_id: 'c2', title: 'Phở bò', url: null, snippet: 'phần 2' },
        ],
      })
      emit({ type: 'done', tokensUsed: 1 })
    })
    fireEvent.click(screen.getByText('Chi tiết nguồn'))
    // Cùng một note xuất hiện 2 chunk (dữ liệu cũ) vẫn đếm 1 ghi chú.
    expect(screen.getByText('1 ghi chú')).toBeTruthy()
    expect(screen.getAllByText('Phở bò').length).toBeGreaterThanOrEqual(2)
  })

  it('nguồn lưu trước Phase 1 (chưa có source_index) vẫn nhóm theo domain, không crash', async () => {
    await ask('hỏi')
    act(() => {
      emit({
        type: 'sources',
        sources: [
          { index: 1, note_id: 'n1', chunk_id: 'c1', title: 'Phở bò', url: null, snippet: 's' },
          { index: 2, note_id: 'n2', chunk_id: 'c2', title: 'Ghi chú tay', url: null, snippet: 's' },
        ] as unknown as ChatSource[],
      })
      emit({ type: 'done', tokensUsed: 1 })
    })
    expect(screen.getByText('Nguồn (1)')).toBeTruthy()
    const labels = [...document.querySelectorAll('.source-cluster-label')].map((el) => el.textContent)
    expect(labels).toEqual(['Không rõ nguồn'])
    expect(document.querySelectorAll('.source-chip')).toHaveLength(2)
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

  it('trạng thái trống gợi ý 3 câu hỏi tổng quan và gửi ngay khi bấm', async () => {
    render(<Harness />)
    expect(screen.getByRole('heading', { name: 'Hỏi AI về ghi chú của bạn' })).toBeTruthy()
    const OVERVIEW = [
      'Tóm tắt những chủ đề chính trong ghi chú của tôi',
      'Ghi chú của tôi tập trung ở những nguồn nào?',
      'Những ý chính nào xuất hiện trong nhiều ghi chú?',
    ]
    for (const q of OVERVIEW) expect(screen.getByRole('button', { name: q })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: OVERVIEW[0]! }))
    await waitFor(() => expect(askChat).toHaveBeenCalled())
    expect(askChat.mock.calls[0]![0]).toMatchObject({ question: OVERVIEW[0] })
  })

  it('composer có hint ngữ cảnh 5 lượt gần nhất trong phiên', async () => {
    render(<Harness />)
    expect(screen.getByText('Ngữ cảnh: 5 lượt gần nhất trong phiên này')).toBeTruthy()
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
  const SOURCE: ChatSource = { index: 1, source_index: 1, source_domain: null, note_id: 'n1', chunk_id: 'c1', title: 'Phở bò', url: null, snippet: 'hầm xương' }

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
