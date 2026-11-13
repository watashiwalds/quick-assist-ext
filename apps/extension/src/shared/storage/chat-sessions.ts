/**
 * Lịch sử hội thoại tab "Hỏi AI" — lưu cục bộ theo phiên trên `chrome.storage.local`.
 *
 * Một key duy nhất (`v: 1`) vì tần suất ghi thấp (2 lần/lượt hỏi–đáp) và đã có cap; IndexedDB hay
 * key-riêng-mỗi-phiên là over-engineering ở quy mô này. UI đọc/ghi trực tiếp; background chỉ xoá
 * khi đăng xuất/xoá tài khoản (R-10). Server vẫn KHÔNG lưu nội dung chat (ADR-0012).
 */
import { type ChatSession, MAX_SESSIONS, capMessages, normalizeRestored } from '../chat'

export const CHAT_SESSIONS_KEY = 'qa.chatSessions'
export const CHAT_SESSIONS_VERSION = 1

export interface ChatSessionsStore {
  v: typeof CHAT_SESSIONS_VERSION
  sessions: ChatSession[]
  activeId: string | null
}

const empty = (): ChatSessionsStore => ({ v: CHAT_SESSIONS_VERSION, sessions: [], activeId: null })

/** Bỏ bản ghi hỏng/thiếu trường; chuẩn hoá stream dở và tin nhắn rỗng khi khôi phục. */
function restoreSession(raw: unknown): ChatSession | null {
  if (!raw || typeof raw !== 'object') return null
  const s = raw as Partial<ChatSession>
  if (typeof s.id !== 'string' || !s.id) return null
  if (!Array.isArray(s.messages)) return null
  const messages = normalizeRestored(capMessages(s.messages))
  if (messages.length === 0) return null
  const now = Date.now()
  return {
    id: s.id,
    title: typeof s.title === 'string' && s.title ? s.title : 'Cuộc trò chuyện',
    messages,
    folderId: typeof s.folderId === 'string' ? s.folderId : null,
    createdAt: typeof s.createdAt === 'number' ? s.createdAt : now,
    updatedAt: typeof s.updatedAt === 'number' ? s.updatedAt : now,
  }
}

export async function loadChatSessions(): Promise<ChatSessionsStore> {
  const raw = (await chrome.storage.local.get(CHAT_SESSIONS_KEY))[CHAT_SESSIONS_KEY]
  if (!raw || typeof raw !== 'object') return empty()
  const data = raw as Partial<ChatSessionsStore>
  if (data.v !== CHAT_SESSIONS_VERSION || !Array.isArray(data.sessions)) return empty()

  let sessions = data.sessions.map(restoreSession).filter((s): s is ChatSession => s !== null)
  sessions.sort((a, b) => b.updatedAt - a.updatedAt)

  // `activeId: null` là trạng thái hợp lệ ("Cuộc trò chuyện mới" chưa hỏi gì) — giữ nguyên.
  let activeId: string | null = null
  if (typeof data.activeId === 'string') {
    const active = sessions.find((s) => s.id === data.activeId)
    if (active) {
      // Phiên đang mở không bị evict oan khi vừa mở lại một phiên cũ.
      sessions = [active, ...sessions.filter((s) => s.id !== active.id)]
    }
    activeId = active ? active.id : (sessions[0]?.id ?? null)
  }

  return { v: CHAT_SESSIONS_VERSION, sessions: sessions.slice(0, MAX_SESSIONS), activeId }
}

export async function saveChatSessions(sessions: ChatSession[], activeId: string | null): Promise<void> {
  const store: ChatSessionsStore = { v: CHAT_SESSIONS_VERSION, sessions: sessions.slice(0, MAX_SESSIONS), activeId }
  await chrome.storage.local.set({ [CHAT_SESSIONS_KEY]: store })
}

/** Xoá sạch lịch sử chat cục bộ (đăng xuất / xoá tài khoản — R-10). */
export async function clearChatSessions(): Promise<void> {
  await chrome.storage.local.remove(CHAT_SESSIONS_KEY)
}

/**
 * Dung lượng lịch sử chat đã dùng và hạn mức của `chrome.storage.local` (mặc định 10 MB — manifest
 * không xin `unlimitedStorage`). Dùng cho footer rail + modal Quản lý của màn Hỏi AI.
 */
export async function chatStorageUsage(): Promise<{ bytes: number; quota: number }> {
  const bytes = await chrome.storage.local.getBytesInUse([CHAT_SESSIONS_KEY])
  return { bytes, quota: chrome.storage.local.QUOTA_BYTES }
}
