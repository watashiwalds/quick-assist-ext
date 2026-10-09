/**
 * Mỗi endpoint backend = 1 hàm ở đây. Đây là chỗ DUY NHẤT trong extension biết URL.
 * Chỉ background được import file này (kiểm tra bởi tests/architecture.test.ts).
 */
import type { HttpRequest } from './http'
import type {
  Folder,
  Note,
  NoteCreate,
  NoteUpdate,
  Quota,
  SearchHit,
  SummaryPreview,
  TokenPair,
  User,
} from './types'

export interface Page<T> {
  items: T[]
  next_cursor: string | null
}

export function createApi(http: HttpRequest) {
  return {
    auth: {
      exchangeGoogle: (b: { code: string; code_verifier: string; redirect_uri: string; nonce: string }) =>
        http<TokenPair>('/auth/google/exchange', { method: 'POST', body: b }),
      refresh: (refresh_token: string) =>
        http<TokenPair>('/auth/refresh', { method: 'POST', body: { refresh_token } }),
      logout: (refresh_token: string) =>
        http<void>('/auth/logout', { method: 'POST', body: { refresh_token } }),
    },
    me: {
      get: () => http<User>('/me'),
      delete: () => http<void>('/me', { method: 'DELETE' }),
      quota: () => http<Quota>('/me/quota'),
    },
    folders: {
      list: () => http<Folder[]>('/folders'),
      create: (name: string) => http<Folder>('/folders', { method: 'POST', body: { name } }),
      rename: (id: string, name: string) => http<Folder>(`/folders/${id}`, { method: 'PATCH', body: { name } }),
      remove: (id: string) => http<void>(`/folders/${id}`, { method: 'DELETE' }),
    },
    notes: {
      create: (b: NoteCreate, idempotencyKey: string) =>
        http<Note>('/notes', { method: 'POST', body: b, headers: { 'Idempotency-Key': idempotencyKey } }),
      list: (q: { folder_id?: string; updated_since?: string; cursor?: string; limit?: number }) =>
        http<Page<Note>>('/notes', { query: q }),
      get: (id: string) => http<Note>(`/notes/${id}`),
      update: (id: string, b: NoteUpdate) => http<Note>(`/notes/${id}`, { method: 'PATCH', body: b }),
      saveSummary: (id: string, version: number, summary_text: string) =>
        http<Note>(`/notes/${id}/summary`, { method: 'PUT', body: { version, summary_text } }),
      remove: (id: string) => http<void>(`/notes/${id}`, { method: 'DELETE' }),
      bulkDelete: (ids: string[]) =>
        http<{ deleted: number }>('/notes/bulk-delete', { method: 'POST', body: { ids } }),
      reindex: (id: string) => http<Note>(`/notes/${id}/reindex`, { method: 'POST' }),
    },
    search: {
      query: (b: { query: string; folder_id?: string | null; top_k?: number }) =>
        http<{ items: SearchHit[] }>('/search', { method: 'POST', body: b }),
    },
    ai: {
      summarize: (b: { text?: string; note_id?: string }) =>
        http<SummaryPreview>('/ai/summaries', { method: 'POST', body: b }),
    },
  }
}

export type Api = ReturnType<typeof createApi>
