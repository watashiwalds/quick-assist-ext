/**
 * HỢP ĐỒNG giao tiếp giữa UI/content ↔ background (ADR-0007).
 *
 * UI và content script KHÔNG gọi API trực tiếp. Chúng gửi RPC tới background —
 * nơi duy nhất giữ token, hàng đợi gửi lại, cache. Thêm tính năng = thêm 1 dòng
 * vào `RpcMap` + 1 handler trong background/handlers.ts; TypeScript sẽ bắt lỗi
 * nếu thiếu handler hoặc sai kiểu.
 */
import type { Folder, Note, Quota, SearchHit, SummaryPreview, User } from '../api/types'
import type { SerializedError } from '../errors'

export interface SessionInfo {
  signedIn: boolean
  user: User | null
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
}

export interface RpcMap {
  'auth/status': { req: void; res: SessionInfo }
  'auth/login': { req: void; res: SessionInfo }
  'auth/logout': { req: void; res: SessionInfo }
  'account/delete': { req: void; res: SessionInfo }
  'quota/get': { req: void; res: Quota }

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
  'notes/reindex': { req: { id: string }; res: Note }

  'quickNote/undo': { req: { pendingId: string }; res: { undone: boolean } }
  'outbox/list': { req: void; res: PendingNote[] }
  'outbox/retry': { req: { id: string }; res: void }
  'outbox/discard': { req: { id: string }; res: void }

  'search/query': { req: { query: string; folderId?: string | null; topK?: number }; res: SearchHit[] }
  'summary/preview': { req: { noteId?: string; text?: string }; res: SummaryPreview }
  'summary/save': { req: { noteId: string; version: number; summary: string }; res: Note }
  /** Lưu vùng chọn thành ghi chú mới kèm bản tóm tắt đã xác nhận. */
  'summary/saveSelection': { req: { text: string; url: string | null; title: string | null; summary: string; folderId?: string | null }; res: Note }
  'selection/takePending': { req: void; res: PendingSelection | null }

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

export function isRpcRequest(m: unknown): m is RpcRequest {
  return typeof m === 'object' && m !== null && (m as RpcRequest).channel === 'qa-rpc'
}

export function isBroadcast(m: unknown): m is BroadcastEvent {
  return typeof m === 'object' && m !== null && (m as BroadcastEvent).channel === 'qa-event'
}
