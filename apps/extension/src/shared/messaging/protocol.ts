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

export interface RpcMap {
  'auth/status': { req: void; res: SessionInfo }
  'auth/login': { req: void; res: SessionInfo }
  'auth/logout': { req: void; res: SessionInfo }
  'account/delete': { req: void; res: SessionInfo }
  'quota/get': { req: void; res: Quota }

  'folders/list': { req: void; res: Folder[] }
  'folders/create': { req: { name: string }; res: Folder }
  'folders/delete': { req: { id: string }; res: void }

  'notes/list': { req: { folderId?: string | null }; res: Note[] }
  'notes/sync': { req: void; res: { changed: number } }
  'notes/update': { req: { id: string; version: number; content?: string; title?: string; folderId?: string }; res: Note }
  'notes/delete': { req: { ids: string[] }; res: { deleted: number } }
  'notes/reindex': { req: { id: string }; res: Note }

  'quickNote/undo': { req: { pendingId: string }; res: { undone: boolean } }

  'search/query': { req: { query: string; folderId?: string | null }; res: SearchHit[] }
  'summary/preview': { req: { noteId?: string; text?: string }; res: SummaryPreview }
  'summary/save': { req: { noteId: string; version: number; summary: string }; res: Note }
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
  | { channel: 'qa-event'; type: 'session/changed'; signedIn: boolean }

export function isRpcRequest(m: unknown): m is RpcRequest {
  return typeof m === 'object' && m !== null && (m as RpcRequest).channel === 'qa-rpc'
}

export function isBroadcast(m: unknown): m is BroadcastEvent {
  return typeof m === 'object' && m !== null && (m as BroadcastEvent).channel === 'qa-event'
}
