// @vitest-environment happy-dom
/** Lịch sử hội thoại theo phiên (X02): lưu/khôi phục, chuyển phiên, stream dở, pagehide, không ghi mỗi delta,
 *  đổi tên / xoá một phiên / xoá tất cả qua rail + modal Quản lý của giao diện mới. */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChatMessageItem, ChatSession } from '../../src/shared/chat'
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
const { useChatSessions } = await import('../../src/ui/features/chat/useChatSessions')

const onOpenNote = vi.fn()

/** Kho giả phía background (UI chỉ nói chuyện qua RPC `chatSessions/*`). */
interface Store {
  sessions: ChatSession[]
  activeId: string | null
}
let store: Store = { sessions: [], activeId: null }
const saveCalls = vi.fn()

/** Giống App: bọc hook + gắn flush vào `pagehide`. */
function Harness() {
  const chat = useChatSessions()
  useEffect(() => {
    const flush = () => chat.flush()
    window.addEventListener('pagehide', flush)
    return () => window.removeEventListener('pagehide', flush)
  }, [chat.flush])
  return (
    <div data-testid="harness" data-ready={chat.ready ? '1' : '0'}>
      <ChatView
        chat={chat}
        ready={chat.ready}
        sessions={chat.sessions}
        activeId={chat.activeId}
        onSwitchSession={chat.switchSession}
        onNewSession={chat.newSession}
        onRenameSession={chat.renameSession}
        onDeleteSession={chat.deleteSession}
        onClearSessions={chat.clearSessions}
        onOpenNote={onOpenNote}
        onGoSettings={() => undefined}
      />
    </div>
  )
}

const user = (id: string, text: string): ChatMessageItem => ({ id, role: 'user', text })
const ai = (id: string, text: string, status: ChatMessageItem['status'] = 'done'): ChatMessageItem => ({
  id,
  role: 'assistant',
  text,
  status,
})
const session = (
  id: string,
  messages: ChatMessageItem[],
  folderId: string | null = null,
  title = 'phiên',
): ChatSession => ({ id, title, messages, folderId, createdAt: 1, updatedAt: 2 })

beforeEach(() => {
  store = { sessions: [], activeId: null }
  saveCalls.mockClear()
  rpc.mockReset()
  rpc.mockImplementation(async (type: string, payload?: unknown) => {
    if (type === 'chatSessions/load') return structuredClone(store)
    if (type === 'chatSessions/save') {
      store = structuredClone(payload as Store)
      saveCalls()
      return undefined
    }
    // `chatSessions/usage`, `folders/list`, … — UI tự bỏ qua dữ liệu lạ.
    return []
  })
  askChat.mockClear()
  stop.mockReset()
  onOpenNote.mockReset()
})
afterEach(cleanup)

async function ready() {
  await waitFor(() => expect(screen.getByTestId('harness').dataset.ready).toBe('1'))
}

async function ask(text: string) {
  fireEvent.change(screen.getByLabelText('Câu hỏi về ghi chú'), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Gửi' }))
  await waitFor(() => expect(askChat).toHaveBeenCalled())
}

function finish(text: string) {
  act(() => {
    emit({ type: 'delta', text })
    emit({ type: 'done', tokensUsed: 1 })
  })
}

/** Phiên đang mở trong rail (aria-current) — thay cho select "Phiên trò chuyện" của bản cũ. */
function activeSessionItem(): HTMLElement {
  return screen.getByRole('button', { current: true })
}

function openManage() {
  fireEvent.click(screen.getByRole('button', { name: /Quản lý/ }))
  return screen.findByRole('dialog', { name: 'Quản lý phiên' })
}

describe('useChatSessions', () => {
  it('lưu phiên khi trả lời xong và khôi phục sau khi mở lại panel', async () => {
    const view = render(<Harness />)
    await ready()
    await ask('câu 1')
    finish('đáp 1')

    await waitFor(() => expect(store.sessions).toHaveLength(1))
    const first = store.sessions[0]!
    expect(first.title).toBe('câu 1')
    expect(store.activeId).toBe(first.id)

    view.unmount()
    render(<Harness />)
    await ready()
    expect(screen.getByText('đáp 1')).toBeTruthy()
    expect(activeSessionItem().getAttribute('aria-label')).toBe('Phiên: câu 1')
  })

  it('tạo phiên mới và chuyển lại phiên cũ trong rail', async () => {
    render(<Harness />)
    await ready()
    await ask('câu 1')
    finish('đáp 1')
    await waitFor(() => expect(store.sessions).toHaveLength(1))
    const first = store.sessions[0]!

    fireEvent.click(screen.getByRole('button', { name: 'Cuộc trò chuyện mới' }))
    await waitFor(() => expect(screen.queryByText('đáp 1')).toBeNull())

    await ask('câu 2')
    finish('đáp 2')
    await waitFor(() => expect(store.sessions).toHaveLength(2))
    const second = store.sessions.find((s) => s.id !== first.id)!
    expect(store.activeId).toBe(second.id)
    expect(activeSessionItem().getAttribute('aria-label')).toBe('Phiên: câu 2')

    fireEvent.click(screen.getByRole('button', { name: 'Phiên: câu 1' }))
    await waitFor(() => expect(screen.getByText('đáp 1')).toBeTruthy())
    expect(screen.queryByText('đáp 2')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Phiên: câu 2' }))
    await waitFor(() => expect(screen.getByText('đáp 2')).toBeTruthy())
  })

  it('chuyển phiên khi đang stream: dừng stream, giữ phần đã nhận dạng "Đã dừng"', async () => {
    store = { sessions: [session('s1', [user('u1', 'hỏi 1'), ai('a1', 'đáp 1', 'done')], null, 'phiên cũ')], activeId: 's1' }
    render(<Harness />)
    await ready()

    await ask('hỏi dở')
    act(() => emit({ type: 'delta', text: 'một phần' }))

    fireEvent.click(screen.getByRole('button', { name: 'Cuộc trò chuyện mới' }))
    expect(stop).toHaveBeenCalled()
    await waitFor(() => expect(screen.queryByText('một phần')).toBeNull())

    const frozen = store.sessions.find((s) => s.id === 's1')!
    expect(frozen.messages.at(-1)?.text).toBe('một phần')
    expect(frozen.messages.at(-1)?.status).toBe('stopped')

    // Phiên cũ mở lại vẫn hiện phần đã nhận + nhãn "Đã dừng".
    fireEvent.click(screen.getByRole('button', { name: 'Phiên: phiên cũ' }))
    await waitFor(() => expect(screen.getByText('một phần')).toBeTruthy())
    expect(screen.getByText('Đã dừng')).toBeTruthy()
  })

  it('khôi phục câu trả lời dở thành "Đã dừng" và giữ phần text', async () => {
    store = { sessions: [session('s1', [user('u', 'hỏi dở'), ai('a', 'một phần', 'streaming')])], activeId: 's1' }
    render(<Harness />)
    await ready()
    expect(screen.getByText('một phần')).toBeTruthy()
    expect(screen.getByText('Đã dừng')).toBeTruthy()
  })

  it('pagehide ghi phần đã stream; mở lại panel không mất chữ', async () => {
    const view = render(<Harness />)
    await ready()
    await ask('hỏi dài')
    act(() => emit({ type: 'delta', text: 'một phần' }))

    // Bản lưu lúc gửi câu hỏi chưa có chữ nào của câu trả lời.
    await waitFor(() => expect(store.sessions).toHaveLength(1))
    expect(store.sessions[0]?.messages).toHaveLength(2)
    expect(store.sessions[0]?.messages.at(-1)?.text).toBe('')

    act(() => void window.dispatchEvent(new Event('pagehide')))
    await waitFor(() => expect(store.sessions[0]?.messages.at(-1)?.text).toBe('một phần'))

    view.unmount()
    render(<Harness />)
    await ready()
    expect(screen.getByText('một phần')).toBeTruthy()
    expect(screen.getByText('Đã dừng')).toBeTruthy()
  })

  it('không ghi storage theo từng delta stream — chỉ khi gửi và khi kết thúc', async () => {
    render(<Harness />)
    await ready()
    await ask('hỏi')
    await waitFor(() => expect(store.sessions).toHaveLength(1))

    const writes = saveCalls.mock.calls.length
    act(() => {
      emit({ type: 'delta', text: 'a' })
      emit({ type: 'delta', text: 'b' })
    })
    await act(async () => {
      await Promise.resolve()
    })
    expect(saveCalls.mock.calls.length).toBe(writes)

    act(() => emit({ type: 'done', tokensUsed: 1 }))
    await waitFor(() => expect(saveCalls.mock.calls.length).toBe(writes + 1))
  })

  it('thư mục của phiên đã bị xoá → rơi về "Tất cả thư mục", không lỗi', async () => {
    store = { sessions: [session('s1', [user('u', 'hỏi'), ai('a', 'đáp')], 'deleted-folder')], activeId: 's1' }
    render(<Harness />)
    await ready()
    expect((screen.getByLabelText('Hỏi trong thư mục') as HTMLSelectElement).value).toBe('')
  })

  it('đổi tên phiên ngay trên header và lưu xuống kho', async () => {
    store = { sessions: [session('s1', [user('u', 'hỏi'), ai('a', 'đáp')], null, 'phiên')], activeId: 's1' }
    render(<Harness />)
    await ready()

    fireEvent.click(screen.getByRole('button', { name: 'Đổi tên' }))
    const input = screen.getByLabelText('Tên cuộc trò chuyện') as HTMLInputElement
    expect(input.value).toBe('phiên')
    fireEvent.change(input, { target: { value: '  Kế hoạch   tuần này  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }))

    await waitFor(() => expect(store.sessions[0]?.title).toBe('Kế hoạch tuần này'))
    expect(screen.getByRole('button', { name: 'Phiên: Kế hoạch tuần này' })).toBeTruthy()
  })

  it('xoá phiên đang mở cần xác nhận rồi mở phiên còn lại', async () => {
    store = {
      sessions: [
        session('s1', [user('u1', 'hỏi 1'), ai('a1', 'đáp 1')], null, 'phiên 1'),
        session('s2', [user('u2', 'hỏi 2'), ai('a2', 'đáp 2')], null, 'phiên 2'),
      ],
      activeId: 's1',
    }
    render(<Harness />)
    await ready()

    fireEvent.click(screen.getByRole('button', { name: 'Xoá' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Xoá phiên' }))

    await waitFor(() => expect(store.sessions.map((s) => s.id)).toEqual(['s2']))
    expect(store.activeId).toBe('s2')
    expect(screen.getByText('đáp 2')).toBeTruthy()
  })

  it('nút xoá trong modal Quản lý đóng modal, xác nhận rồi xoá đúng phiên', async () => {
    store = {
      sessions: [
        session('s1', [user('u1', 'hỏi 1'), ai('a1', 'đáp 1')], null, 'phiên 1'),
        session('s2', [user('u2', 'hỏi 2'), ai('a2', 'đáp 2')], null, 'phiên 2'),
      ],
      activeId: 's1',
    }
    render(<Harness />)
    await ready()

    await openManage()
    fireEvent.click(screen.getByRole('button', { name: 'Xoá phiên phiên 2' }))
    // Chỉ một dialog mở tại một thời điểm.
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Quản lý phiên' })).toBeNull())
    fireEvent.click(await screen.findByRole('button', { name: 'Xoá phiên' }))

    await waitFor(() => expect(store.sessions.map((s) => s.id)).toEqual(['s1']))
    expect(screen.getByText('đáp 1')).toBeTruthy()
  })

  it('xoá tất cả cần gõ XOÁ và đưa hội thoại về trạng thái mới', async () => {
    store = {
      sessions: [session('s1', [user('u1', 'hỏi 1'), ai('a1', 'đáp 1')], null, 'phiên 1')],
      activeId: 's1',
    }
    render(<Harness />)
    await ready()

    await openManage()
    fireEvent.click(screen.getByRole('button', { name: /Xoá tất cả/ }))
    const confirm = await screen.findByRole('button', { name: 'Xoá tất cả' })
    expect((confirm as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(screen.getByLabelText(/Gõ “XOÁ”/), { target: { value: 'XOÁ' } })
    fireEvent.click(confirm)

    await waitFor(() => expect(store.sessions).toHaveLength(0))
    expect(store.activeId).toBeNull()
    expect(screen.queryByText('đáp 1')).toBeNull()
    expect(screen.getByText('Hỏi AI về ghi chú của bạn')).toBeTruthy()
  })

  it('lọc phiên theo tiêu đề trong rail', async () => {
    store = {
      sessions: [
        session('s1', [user('u1', 'hỏi'), ai('a1', 'đáp')], null, 'Kubernetes'),
        session('s2', [user('u2', 'hỏi'), ai('a2', 'đáp')], null, 'Nấu phở'),
      ],
      activeId: 's1',
    }
    render(<Harness />)
    await ready()

    fireEvent.change(screen.getByLabelText('Tìm phiên hội thoại'), { target: { value: 'phở' } })
    expect(screen.getByRole('button', { name: 'Phiên: Nấu phở' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Phiên: Kubernetes' })).toBeNull()

    fireEvent.change(screen.getByLabelText('Tìm phiên hội thoại'), { target: { value: 'không có' } })
    expect(screen.getByText('Không tìm thấy phiên nào')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Xoá tìm kiếm' }))
    expect(screen.getByRole('button', { name: 'Phiên: Kubernetes' })).toBeTruthy()
  })
})
