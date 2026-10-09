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
export type SearchHit = S['SearchHitOut']
export type TokenPair = S['TokenPairOut']
export type Quota = S['QuotaOut']
export type User = S['UserOut']
export type SummaryPreview = S['SummaryOut']
export type IndexStatus = Note['index_status']
