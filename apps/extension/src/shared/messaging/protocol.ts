/**
 * HỢP ĐỒNG giao tiếp giữa UI/content ↔ background (ADR-0007).
 *
 * UI và content script KHÔNG gọi API trực tiếp. Chúng gửi RPC tới background —
 * nơi duy nhất giữ token, hàng đợi gửi lại, cache. Thêm tính năng = thêm 1 dòng
 * vào `RpcMap` + 1 handler trong background/handlers.ts; TypeScript sẽ bắt lỗi
 * nếu thiếu handler hoặc sai kiểu.
 */
import type {
  AiSettings,
  AiSettingsInput,
  AiTestInput,
  AiTestResult,
  AuthConfig,
  ChatSource,
  ChatTurn,
  Folder,
  Note,
  PageMatchResult,
  Quota,
  SearchSource,
  SummaryPreview,
  User,
} from '../api/types'
import type { ChatSession } from '../chat'
import type { SerializedError } from '../errors'

export interface SessionInfo {
  signedIn: boolean
  user: User | null
  /** Chế độ xác thực của server (ADR-0016): local = tự host một người, không có Google. */
  authMode: 'google' | 'local'
}

/** Ghi chú nhanh chưa lên server (đang chờ hoàn tác / mất mạng / lỗi). Không trả toàn văn. */
export interface PendingNote {
  id: string
  snippet: string
  url: string | null
  title: string | null
  folderId: string | null
  createdAt: number
  attempts: number
  lastError?: string
  /** 'queued' = sẽ tự gửi lại; 'failed' = lỗi không tự khắc phục, cần người dùng chọn */
  state: 'queued' | 'failed'
}

/** Vùng chọn người dùng muốn tóm tắt (menu chuột phải → side panel). */
export interface PendingSelection {
  text: string
  url: string | null
  title: string | null
  truncated: boolean
  at: number
}

export interface Preferences {
  /** Thư mục mặc định khi lưu nhanh bằng phím tắt / mục "Ghi chú văn bản này". null = Inbox */
  defaultFolderId: string | null
  /** Tab "Tìm kiếm" đã gộp vào thanh tìm của Thư viện — ẩn mặc định, bật lại trong Cài đặt. */
  showSearchTab: boolean
}

/** Kết quả quét (AutoChunk) + tab đã quét (để highlight đúng tab dù người dùng chuyển tab).
 *  `tabId` chỉ có khi nguồn là trang đang mở; nội dung dán không có trang gốc nên `url` = null. */
export type PageMatchRun = PageMatchResult & { tabId?: number; url: string | null; title: string | null }

export interface RpcMap {
  'auth/status': { req: void; res: SessionInfo }
  'auth/login': { req: void; res: SessionInfo }
  'auth/logout': { req: void; res: SessionInfo }
  'account/delete': { req: void; res: SessionInfo }
  'quota/get': { req: void; res: Quota }
  /** Tạo lại hạn mức (môi trường demo hoặc user BYOK — ADR-0016 D6). */
  'quota/reset': { req: void; res: Quota }

  /** Nhà cung cấp AI per-user (BYOK, ADR-0016 §6). Response không bao giờ chứa key. */
  'ai/config/get': { req: void; res: AiSettings }
  /** Lưu cấu hình; fingerprint embedding đổi → server tự rebuild và trả `rebuild` trong res. */
  'ai/config/set': { req: AiSettingsInput; res: AiSettings }
  /** Về dùng cấu hình server (mode=inherit); key bị xoá khỏi DB. */
  'ai/config/reset': { req: void; res: AiSettings }
  /** Kiểm tra kết nối embed + chat (timeout 30s). Không bắt buộc trước khi lưu. */
  'ai/config/test': { req: AiTestInput; res: AiTestResult }

  'prefs/get': { req: void; res: Preferences }
  'prefs/set': { req: Partial<Preferences>; res: Preferences }

  'folders/list': { req: void; res: Folder[] }
  'folders/create': { req: { name: string }; res: Folder }
  'folders/rename': { req: { id: string; name: string }; res: Folder }
  'folders/delete': { req: { id: string }; res: void }

  'notes/list': { req: { folderId?: string | null }; res: Note[] }
  'notes/get': { req: { id: string }; res: Note }
  'notes/sync': { req: void; res: { changed: number } }
  'notes/update': { req: { id: string; version: number; content?: string; title?: string; folderId?: string }; res: Note }
  'notes/delete': { req: { ids: string[] }; res: { deleted: number } }
  /** Phase 2 — chuyển các ghi chú ĐÃ CHỌN sang thư mục đích (null → Inbox). */
  'notes/move': { req: { ids: string[]; folderId: string | null }; res: { moved: number; missing: string[] } }
  'notes/reindex': { req: { id: string }; res: Note }

  'quickNote/undo': { req: { pendingId: string }; res: { undone: boolean } }
  'outbox/list': { req: void; res: PendingNote[] }
  'outbox/retry': { req: { id: string }; res: void }
  'outbox/discard': { req: { id: string }; res: void }

  /** Kết quả grouped theo nguồn (Phase 1 contract; Phase 2 UI dùng thẳng).
   * `maxSources` = số nguồn (domain) tối đa; mỗi nguồn API trả tối đa 10 note. */
  'search/query': { req: { query: string; folderId?: string | null; maxSources?: number }; res: SearchSource[] }
  'summary/preview': { req: { noteId?: string; text?: string }; res: SummaryPreview }
  'summary/save': { req: { noteId: string; version: number; summary: string }; res: Note }
  /** Lưu vùng chọn thành ghi chú mới kèm bản tóm tắt đã xác nhận. */
  'summary/saveSelection': { req: { text: string; url: string | null; title: string | null; summary: string; folderId?: string | null }; res: Note }
  'selection/takePending': { req: void; res: PendingSelection | null }

  /** Tạo ghi chú mới từ UI (AutoChunk lưu các đoạn đã chọn) — background sinh Idempotency-Key. */
  'notes/create': { req: { content: string; title: string | null; url: string | null; folderId?: string | null }; res: Note }
  /** AutoChunk: ước lượng độ dài văn bản trang trước khi quét (không tải HTML lên server). */
  'pageMatch/inspect': { req: void; res: { textChars: number; url: string; title: string } }
  /** AutoChunk: quét tab đang xem hoặc nội dung dán (`text`) theo truy vấn (POST /ai/page-match/stream).
   *  `scanAll` = bỏ trần 50k, chia lô; `requestId` để UI huỷ giữa chừng qua `pageMatch/cancel`. */
  'pageMatch/run': { req: { query: string; text?: string; scanAll?: boolean; requestId?: string }; res: PageMatchRun }
  /** AutoChunk: huỷ lần quét đang chạy (đóng fetch, server release quota giữ chỗ). */
  'pageMatch/cancel': { req: { requestId: string }; res: void }
  /** AutoChunk: cuộn tới + làm nổi bật các đoạn trên trang đã quét. */
  'pageMatch/highlight': { req: { tabId: number; items: Array<{ text: string; occ: number }> }; res: { ok: boolean; found: number; total: number } }

  /** Lịch sử chat theo phiên (X02) — UI không đọc/ghi storage trực tiếp; background sở hữu key. */
  'chatSessions/load': { req: void; res: { sessions: ChatSession[]; activeId: string | null } }
  'chatSessions/save': { req: { sessions: ChatSession[]; activeId: string | null }; res: void }
  /** Dung lượng key lịch sử chat trên `chrome.storage.local` (footer rail + modal Quản lý). */
  'chatSessions/usage': { req: void; res: { bytes: number; quota: number } }

  /** Chỉ có trong bản build E2E (VITE_E2E=true) — bản phát hành trả lỗi E2E_ONLY. */
  'e2e/devLogin': { req: { email: string }; res: SessionInfo }
}

export type RpcType = keyof RpcMap
export type RpcReq<K extends RpcType> = RpcMap[K]['req']
export type RpcRes<K extends RpcType> = RpcMap[K]['res']

export interface RpcRequest<K extends RpcType = RpcType> {
  channel: 'qa-rpc'
  type: K
  payload: RpcReq<K>
}

export type RpcResponse<T> = { ok: true; data: T } | { ok: false; error: SerializedError }

/** Sự kiện background phát cho mọi UI đang mở (chrome.runtime.sendMessage). */
export type BroadcastEvent =
  | { channel: 'qa-event'; type: 'notes/changed' }
  | { channel: 'qa-event'; type: 'folders/changed' }
  | { channel: 'qa-event'; type: 'outbox/changed' }
  | { channel: 'qa-event'; type: 'selection/pending' }
  | { channel: 'qa-event'; type: 'session/changed'; signedIn: boolean }
  /** AutoChunk: tiến độ quét — extract → batch i/n → verify (SSE từ server). */
  | { channel: 'qa-event'; type: 'pageMatch/progress'; phase: 'extract' | 'batch' | 'verify'; index?: number; total?: number }

export function isRpcRequest(m: unknown): m is RpcRequest {
  return typeof m === 'object' && m !== null && (m as RpcRequest).channel === 'qa-rpc'
}

export function isBroadcast(m: unknown): m is BroadcastEvent {
  return typeof m === 'object' && m !== null && (m as BroadcastEvent).channel === 'qa-event'
}

/**
 * Chat RAG (X02, ADR-0009): câu trả lời về từng phần nên KHÔNG đi qua RPC một-lần.
 * UI mở `chrome.runtime.connect({ name: CHAT_PORT })` cho mỗi câu hỏi, gửi `ask`; background đọc SSE
 * từ POST /ai/chat và đẩy từng sự kiện về qua Port. `stop` hoặc đóng Port → background huỷ request
 * (server chỉ trừ quota phần đã sinh).
 */
export const CHAT_PORT = 'qa-chat'

export type ChatClientMessage =
  | { type: 'ask'; question: string; folderId?: string | null; history: ChatTurn[] }
  | { type: 'stop' }

export type ChatPortEvent =
  | { type: 'sources'; sources: ChatSource[] }
  | { type: 'delta'; text: string }
  | { type: 'done'; tokensUsed: number }
  | { type: 'stopped' }
  | { type: 'error'; error: SerializedError }
