/**
 * Kiểu dữ liệu API dùng trong extension — lấy từ OpenAPI sinh tự động
 * (`npm run gen:api` → schema.d.ts). KHÔNG tự gõ lại interface khi backend đổi:
 * chạy lại gen:api, TypeScript sẽ báo chỗ cần sửa.
 */
import type { components } from './schema'

type S = components['schemas']

export type Note = S['NoteOut']
export type NoteCreate = S['NoteCreateIn']
export type NoteUpdate = S['NoteUpdateIn']
export type Folder = S['FolderOut']
/** Kết quả tìm kiếm grouped theo nguồn (Phase 1, UX plan §6.1) — dùng cho UI Phase 2. */
export type SearchSource = S['SearchSourceOut']
export type SearchNote = S['SearchNoteOut']
/** Chuyển tiếp (Phase 1): kết quả phẳng cho UI hiện tại — background phẳng hoá từ
 * `SearchSource[]`; Phase 2 đổi UI sang grouped rồi xoá kiểu này. */
export interface SearchHit {
  note_id: string
  note_title: string | null
  note_url: string | null
  text: string
  score: number
  similarity: number
}
export type TokenPair = S['TokenPairOut']
export type Quota = S['QuotaOut']
export type User = S['UserOut']
export type SummaryPreview = S['SummaryOut']
export type IndexStatus = Note['index_status']
export type PageMatchRequest = S['PageMatchIn']
export type PageMatchResult = S['PageMatchOut']
export type PageMatchItem = S['PageMatchItemOut']

export type ChatRequest = S['ChatIn']
export type ChatTurn = S['ChatTurnIn']

/** Cấu hình AI per-user (BYOK, ADR-0016) — không bao giờ chứa key (chỉ has_key + key_hint). */
export type AiSettings = S['AISettingsOut']
export type AiSettingsInput = S['AISettingsIn']
export type AiTestInput = S['AISTestIn']
export type AiTestResult = S['AISTestOut']
export type AiTestEmbedding = S['EmbeddingTestOut']
export type AiTestChat = S['ChatTestOut']
export type AiRebuild = S['AIRebuildOut']
export type ServerDefault = S['ServerDefaultOut']
export type AuthConfig = S['AuthConfigOut']
export type AiProvider = NonNullable<AiSettings['provider']>

/** Dữ liệu sự kiện SSE `sources` của POST /ai/chat (luồng SSE nên không có trong OpenAPI components).
 * Phase 1: `index` là số trích dẫn [n] theo note (liên tục); `source_index`/`source_domain` để nhóm
 * chip theo nguồn (UI Phase 4). */
export interface ChatSource {
  index: number
  source_index: number
  source_domain: string | null
  note_id: string
  chunk_id: string
  title: string | null
  url: string | null
  snippet: string
}
