// @vitest-environment happy-dom
/** Lịch sử hội thoại theo phiên (X02): lưu/khôi phục, chuyển phiên, stream dở, pagehide, không ghi mỗi delta. */
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
        sessions={chat.sessions}
        activeId={chat.activeId}
        onSwitchSession={chat.switchSession}
        onNewSession={chat.newSession}
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
const session = (id: string, messages: ChatMessageItem[], folderId: string | null = null): ChatSession => ({
  id,
  title: 'phiên',
  messages,
  folderId,
  createdAt: 1,
  updatedAt: 2,
})

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
    expect((screen.getByLabelText('Phiên trò chuyện') as HTMLSelectElement).value).toBe(first.id)
  })

  it('tạo phiên mới và chuyển lại phiên cũ qua dropdown', async () => {
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

    const select = screen.getByLabelText('Phiên trò chuyện') as HTMLSelectElement
    fireEvent.change(select, { target: { value: first.id } })
    await waitFor(() => expect(screen.getByText('đáp 1')).toBeTruthy())
    expect(screen.queryByText('đáp 2')).toBeNull()

    fireEvent.change(select, { target: { value: second.id } })
    await waitFor(() => expect(screen.getByText('đáp 2')).toBeTruthy())
  })

  it('khôi phục câu trả lời dở thành "(đã dừng)" và giữ phần text', async () => {
    store = { sessions: [session('s1', [user('u', 'hỏi dở'), ai('a', 'một phần', 'streaming')])], activeId: 's1' }
    render(<Harness />)
    await ready()
    expect(screen.getByText('một phần')).toBeTruthy()
    expect(screen.getByText('(đã dừng)')).toBeTruthy()
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
    expect(screen.getByText('(đã dừng)')).toBeTruthy()
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

  it('thư mục của phiên đã bị xoá → rơi về "Trong mọi thư mục", không lỗi', async () => {
    store = { sessions: [session('s1', [user('u', 'hỏi'), ai('a', 'đáp')], 'deleted-folder')], activeId: 's1' }
    render(<Harness />)
    await ready()
    expect((screen.getByLabelText('Hỏi trong thư mục') as HTMLSelectElement).value).toBe('')
  })
})
