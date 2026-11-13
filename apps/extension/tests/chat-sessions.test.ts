/** Hàm thuần + storage lịch sử chat theo phiên (X02) — không cần React. */
import { beforeEach, describe, expect, it } from 'vitest'
import {
  type ChatMessageItem,
  type ChatSession,
  capMessages,
  evictSessions,
  firstQuestion,
  normalizeRestored,
  sessionTitle,
} from '../src/shared/chat'
import { CHAT_SESSIONS_KEY, clearChatSessions, loadChatSessions, saveChatSessions } from '../src/shared/storage/chat-sessions'
import { installChrome } from './helpers/chrome'

installChrome()

const user = (id: string, text: string): ChatMessageItem => ({ id, role: 'user', text })
const ai = (id: string, text: string, status: ChatMessageItem['status'] = 'done'): ChatMessageItem => ({
  id,
  role: 'assistant',
  text,
  status,
})
const session = (id: string, updatedAt: number, messages: ChatMessageItem[] = [user('u', 'hỏi'), ai('a', 'đáp')]): ChatSession => ({
  id,
  title: id,
  messages,
  folderId: null,
  createdAt: updatedAt,
  updatedAt,
})

beforeEach(async () => {
  await chrome.storage.local.clear()
})

describe('sessionTitle', () => {
  it('gộp khoảng trắng và cắt ~60 ký tự', () => {
    expect(sessionTitle('  cách   nấu phở? ')).toBe('cách nấu phở?')
    const long = 'a'.repeat(80)
    const title = sessionTitle(long)
    expect(title).toHaveLength(60)
    expect(title.endsWith('…')).toBe(true)
  })

  it('câu hỏi rỗng → nhãn mặc định', () => {
    expect(sessionTitle('   ')).toBe('Cuộc trò chuyện')
    expect(firstQuestion([ai('a', 'đáp')])).toBe('')
  })
})

describe('capMessages', () => {
  it('giữ nguyên khi chưa vượt cap', () => {
    const messages = [user('u1', 'hỏi'), ai('a1', 'đáp')]
    expect(capMessages(messages, 4)).toBe(messages)
  })

  it('cắt từ đầu nhưng luôn bắt đầu bằng câu hỏi (giữ trọn cặp)', () => {
    const messages = [user('u1', 'hỏi 1'), ai('a1', 'đáp 1'), user('u2', 'hỏi 2'), ai('a2', 'đáp 2'), user('u3', 'hỏi 3'), ai('a3', 'đáp 3')]
    const capped = capMessages(messages, 4)
    expect(capped.map((m) => m.id)).toEqual(['u2', 'a2', 'u3', 'a3'])
  })

  it('cap lẻ rơi vào giữa cặp → bỏ thêm câu trả lời mồ côi', () => {
    const messages = [user('u1', 'hỏi 1'), ai('a1', 'đáp 1'), user('u2', 'hỏi 2'), ai('a2', 'đáp 2'), user('u3', 'hỏi 3')]
    const capped = capMessages(messages, 4)
    expect(capped.map((m) => m.id)).toEqual(['u2', 'a2', 'u3'])
  })
})

describe('normalizeRestored', () => {
  it('streaming → stopped, bỏ trả lời rỗng, giữ lỗi và phần text đã nhận', () => {
    const messages: ChatMessageItem[] = [
      user('u1', 'hỏi 1'),
      ai('a1', 'một phần', 'streaming'),
      user('u2', 'hỏi 2'),
      ai('a2', '', 'streaming'),
      user('u3', 'hỏi 3'),
      { id: 'a3', role: 'assistant', text: '', status: 'error', error: { code: 'NO_BACKGROUND', message: 'mất kết nối', status: 0 } },
    ]
    const restored = normalizeRestored(messages)
    expect(restored.map((m) => m.id)).toEqual(['u1', 'a1', 'u2', 'u3', 'a3'])
    expect(restored.find((m) => m.id === 'a1')?.status).toBe('stopped')
    // Không sửa mảng gốc (state React còn dùng).
    expect(messages.find((m) => m.id === 'a1')?.status).toBe('streaming')
  })
})

describe('evictSessions', () => {
  it('giữ 20 phiên đầu (mới nhất) và không đổi mảng nhỏ', () => {
    const many = Array.from({ length: 22 }, (_, i) => session(`s${i}`, 100 - i))
    expect(evictSessions(many).map((s) => s.id)).toEqual(many.slice(0, 20).map((s) => s.id))
    const few = many.slice(0, 3)
    expect(evictSessions(few)).toBe(few)
  })
})

describe('storage chat-sessions', () => {
  it('lưu → đọc lại đúng phiên, activeId và thư mục', async () => {
    const sessions = [session('s2', 200), { ...session('s1', 100), folderId: 'f1' }]
    await saveChatSessions(sessions, 's1')
    const store = await loadChatSessions()
    // Phiên đang mở được đưa lên đầu để không bị evict khi vừa mở lại một phiên cũ.
    expect(store.sessions.map((s) => s.id)).toEqual(['s1', 's2'])
    expect(store.activeId).toBe('s1')
    expect(store.sessions.find((s) => s.id === 's1')?.folderId).toBe('f1')
  })

  it('activeId null được giữ nguyên dù còn phiên cũ (đang ở "Cuộc trò chuyện mới")', async () => {
    await saveChatSessions([session('s1', 100)], null)
    const store = await loadChatSessions()
    expect(store.sessions).toHaveLength(1)
    expect(store.activeId).toBeNull()
  })

  it('activeId không còn tồn tại → rơi về phiên mới nhất', async () => {
    await saveChatSessions([session('s1', 100), session('s2', 200)], 'missing')
    expect((await loadChatSessions()).activeId).toBe('s2')
  })

  it('dữ liệu hỏng/sai phiên bản → kho rỗng, không ném lỗi', async () => {
    await chrome.storage.local.set({ [CHAT_SESSIONS_KEY]: { v: 99, sessions: [session('s1', 1)] } })
    expect(await loadChatSessions()).toMatchObject({ sessions: [], activeId: null })

    await chrome.storage.local.set({ [CHAT_SESSIONS_KEY]: 'rác' })
    expect(await loadChatSessions()).toMatchObject({ sessions: [], activeId: null })
  })

  it('khôi phục: stream dở → stopped, bỏ phiên không còn tin nhắn', async () => {
    const broken = { ...session('s1', 100, [user('u', 'hỏi'), ai('a', 'một phần', 'streaming')]) }
    const empty = { ...session('s2', 200, [ai('a2', '', 'streaming')]) }
    await chrome.storage.local.set({ [CHAT_SESSIONS_KEY]: { v: 1, sessions: [broken, empty], activeId: 's1' } })
    const store = await loadChatSessions()
    expect(store.sessions).toHaveLength(1)
    expect(store.sessions[0]?.messages.at(-1)?.status).toBe('stopped')
    expect(store.activeId).toBe('s1')
  })

  it('evict còn tối đa 20 phiên khi đọc', async () => {
    await saveChatSessions(Array.from({ length: 25 }, (_, i) => session(`s${i}`, 1000 - i)), 's0')
    expect((await loadChatSessions()).sessions).toHaveLength(20)
  })

  it('clearChatSessions xoá sạch key (đăng xuất — R-10)', async () => {
    await saveChatSessions([session('s1', 100)], 's1')
    await clearChatSessions()
    expect((await loadChatSessions()).sessions).toEqual([])
    expect((await chrome.storage.local.get(CHAT_SESSIONS_KEY))[CHAT_SESSIONS_KEY]).toBeUndefined()
  })
})
