/**
 * Mỗi endpoint backend = 1 hàm ở đây. Đây là chỗ DUY NHẤT trong extension biết URL.
 * Chỉ background được import file này (kiểm tra bởi tests/architecture.test.ts).
 */
import { config } from '../config'
import type { HttpRequest } from './http'
import type {
  AiSettings,
  AiSettingsInput,
  AiTestInput,
  AiTestResult,
  AuthConfig,
  Folder,
  Note,
  NoteCreate,
  NoteUpdate,
  PageMatchRequest,
  PageMatchResult,
  Quota,
  SearchSource,
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
      /**
       * Đăng nhập dev: bản build E2E truyền email riêng từng test (server dev/test dùng email
       * client); ở chế độ self-host AUTH_MODE=local server BỎ QUA email client gửi và luôn dùng
       * LOCAL_AUTH_EMAIL (ADR-0016 §4.8) → không truyền email.
       */
      devLogin: (email?: string) =>
        http<TokenPair>('/auth/dev-login', { method: 'POST', body: email ? { email } : {} }),
      config: () => http<AuthConfig>('/auth/config'),
    },
    me: {
      get: () => http<User>('/me'),
      delete: () => http<void>('/me', { method: 'DELETE' }),
      quota: () => http<Quota>('/me/quota'),
      resetQuota: () => http<Quota>('/me/quota/reset', { method: 'POST' }),
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
      query: (b: { query: string; folder_id?: string | null; max_sources?: number }) =>
        http<{ sources: SearchSource[] }>('/search', { method: 'POST', body: b }),
    },
    ai: {
      summarize: (b: { text?: string; note_id?: string }) =>
        http<SummaryPreview>('/ai/summaries', { method: 'POST', body: b, timeoutMs: config.summaryRequestTimeoutMs }),
      /** AutoChunk: Trafilatura + embed + LLM thẩm định có thể lâu hơn timeout mặc định. */
      pageMatch: (b: PageMatchRequest) =>
        http<PageMatchResult>('/ai/page-match', { method: 'POST', body: b, timeoutMs: config.pageMatchRequestTimeoutMs }),
    },
    aiSettings: {
      get: () => http<AiSettings>('/me/ai-settings'),
      set: (b: AiSettingsInput) => http<AiSettings>('/me/ai-settings', { method: 'PUT', body: b }),
      remove: () => http<AiSettings>('/me/ai-settings', { method: 'DELETE' }),
      test: (b: AiTestInput) => http<AiTestResult>('/me/ai-settings/test', { method: 'POST', body: b }),
    },
  }
}

export type Api = ReturnType<typeof createApi>
