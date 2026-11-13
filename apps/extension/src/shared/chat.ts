/**
 * Kiểu dữ liệu + hàm thuần cho tab "Hỏi AI" (X02, ADR-0012).
 *
 * Tách khỏi `useChat` để (1) unit-test không cần React/chrome, (2) tầng dữ liệu dùng lại được
 * khi redesign UI phiên chat. Lịch sử vẫn chỉ nằm trên máy người dùng — server không lưu nội dung chat.
 */
import type { ChatSource } from './api/types'
import type { SerializedError } from './errors'

/** Một tin nhắn trong hội thoại. `streaming` chỉ tồn tại khi panel còn mở. */
export interface ChatMessageItem {
  id: string
  role: 'user' | 'assistant'
  text: string
  sources?: ChatSource[]
  status?: 'streaming' | 'done' | 'stopped' | 'error'
  error?: SerializedError
}

/** Một phiên hội thoại lưu cục bộ. `updatedAt` dùng để sắp xếp/evict. */
export interface ChatSession {
  id: string
  title: string
  messages: ChatMessageItem[]
  /** Thư mục lọc lúc hỏi — khôi phục kèm phiên; thư mục đã bị xoá thì UI rơi về "Trong mọi thư mục". */
  folderId: string | null
  createdAt: number
  updatedAt: number
}

/** Giữ tối đa 20 phiên gần nhất (mới nhất đứng đầu mảng). */
export const MAX_SESSIONS = 20
/** Giữ tối đa 20 cặp hỏi–đáp mỗi phiên. */
export const MAX_MESSAGES_PER_SESSION = 40
/** Tiêu đề phiên = câu hỏi đầu, cắt còn ~60 ký tự. */
export const SESSION_TITLE_MAX = 60

export function newSessionId(): string {
  return `s${crypto.randomUUID()}`
}

/** Tiêu đề phiên: gộp khoảng trắng, cắt ~60 ký tự; câu hỏi rỗng → nhãn mặc định. */
export function sessionTitle(question: string): string {
  const text = question.replace(/\s+/g, ' ').trim()
  if (!text) return 'Cuộc trò chuyện'
  if (text.length <= SESSION_TITLE_MAX) return text
  return `${text.slice(0, SESSION_TITLE_MAX - 1).trimEnd()}…`
}

/** Tin nhắn đầu tiên của người dùng — nguồn cho tiêu đề phiên. */
export function firstQuestion(messages: ChatMessageItem[]): string {
  return messages.find((m) => m.role === 'user')?.text ?? ''
}

/**
 * Cắt bớt đầu mảng nhưng giữ nguyên cặp hỏi–đáp: luôn bắt đầu bằng tin nhắn người dùng.
 * Mảng rỗng/không tìm được mốc an toàn → trả mảng rỗng (thà mất phiên còn hơn mất câu hỏi).
 */
export function capMessages(messages: ChatMessageItem[], cap = MAX_MESSAGES_PER_SESSION): ChatMessageItem[] {
  if (messages.length <= cap) return messages
  let start = messages.length - cap
  while (start < messages.length && messages[start]?.role !== 'user') start++
  return start < messages.length ? messages.slice(start) : []
}

/**
 * Chuẩn hoá hội thoại đọc từ storage:
 *  - `streaming` → `stopped` (Port SSE chết theo panel, không hứa tiếp tục stream); giữ phần text đã nhận.
 *  - Bỏ câu trả lời rỗng (stream bị cắt trước khi có chữ); giữ tin nhắn lỗi để người dùng thấy lý do.
 */
export function normalizeRestored(messages: ChatMessageItem[]): ChatMessageItem[] {
  return messages
    .map((m) => (m.role === 'assistant' && m.status === 'streaming' ? { ...m, status: 'stopped' as const } : m))
    .filter((m) => m.role === 'user' || m.text.trim() !== '' || m.status === 'error')
}

/** FIFO: giữ `max` phiên đầu mảng (mới nhất); phiên đang mở luôn được đưa lên đầu trước khi gọi. */
export function evictSessions(sessions: ChatSession[], max = MAX_SESSIONS): ChatSession[] {
  return sessions.length <= max ? sessions : sessions.slice(0, max)
}
