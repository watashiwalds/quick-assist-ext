/**
 * Gom ghi chú theo NGUỒN cho danh sách Thư viện (Phase 2 — UX plan §5.2, D2 — tài liệu nhiều part).
 *
 * Khoá gom = `document_id ?? domain`:
 *  - Tài liệu nhiều part (`document_id`) → MỘT mục, nhãn lấy title part 0; các part xếp theo
 *    `part_index`; chọn/xoá/chuyển tác động lên toàn bộ part.
 *  - Ghi chú cũ/đơn lẻ → gom theo `domain` như trước; không có domain vào "Không rõ nguồn" (cuối).
 *
 * Nhóm xếp theo số MỤC rồi lần cập nhật gần nhất; trong nhóm xếp mới nhất trước.
 * Hàm thuần, không I/O → unit test độc lập.
 */
import type { Note } from '@/shared/api/types'

export const UNKNOWN_SOURCE_LABEL = 'Không rõ nguồn'
const GROUP_SUMMARY_CHARS = 160

/** Một mục trong danh sách: ghi chú đơn hoặc cả tài liệu nhiều part. */
export interface NoteEntry {
  /** `document_id` hoặc `id` của ghi chú đơn — duy nhất trong danh sách. */
  key: string
  /** Part 0 (hoặc ghi chú đơn) — dùng để hiển thị thẻ. */
  note: Note
  /** Toàn bộ part theo `part_index`; ghi chú đơn có đúng 1 phần tử. */
  notes: Note[]
  isDocument: boolean
}

export interface NoteSourceGroup {
  /** Khoá nhóm: `document_id` hoặc domain (null = không rõ nguồn). */
  key: string
  domain: string | null
  label: string
  kind: 'source' | 'document'
  /** Tất cả note/part trong nhóm — dùng cho "Chọn cả nhóm". */
  notes: Note[]
  entries: NoteEntry[]
  /** Tóm tắt ghép từ tối đa 2 mục (summary_text, fallback excerpt) — KHÔNG gọi AI. */
  summary: string | null
}

const latest = (notes: Note[]) =>
  notes.reduce((max, n) => (n.updated_at > max ? n.updated_at : max), '')

/** Một tài liệu = các part cùng `document_id`, part_index tăng dần. */
function toDocumentEntry(parts: Note[]): NoteEntry {
  const notes = [...parts].sort((a, b) => a.part_index - b.part_index)
  const note = notes.find((n) => n.part_index === 0) ?? notes[0]!
  return { key: note.document_id!, note, notes, isDocument: true }
}

export function groupNotesBySource(notes: Note[]): NoteSourceGroup[] {
  const documents = new Map<string, Note[]>()
  const byDomain = new Map<string | null, Note[]>()

  for (const n of notes) {
    if (n.document_id) {
      const list = documents.get(n.document_id)
      if (list) list.push(n)
      else documents.set(n.document_id, [n])
    } else {
      const domain = n.domain?.trim() || null
      const list = byDomain.get(domain)
      if (list) list.push(n)
      else byDomain.set(domain, [n])
    }
  }

  const groups: NoteSourceGroup[] = []

  for (const parts of documents.values()) {
    const entry = toDocumentEntry(parts)
    const title = entry.note.title?.trim()
    groups.push({
      key: entry.key,
      domain: entry.note.domain?.trim() || null,
      label: title || entry.note.domain?.trim() || UNKNOWN_SOURCE_LABEL,
      kind: 'document',
      notes: entry.notes,
      entries: [entry],
      summary: groupSummary(entry.notes),
    })
  }

  for (const [domain, list] of byDomain) {
    const sorted = [...list].sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    groups.push({
      key: domain ?? '__unknown__',
      domain,
      label: domain ?? UNKNOWN_SOURCE_LABEL,
      kind: 'source',
      notes: sorted,
      entries: sorted.map((note) => ({ key: note.id, note, notes: [note], isDocument: false })),
      summary: groupSummary(sorted),
    })
  }

  return groups.sort((a, b) => {
    // "Không rõ nguồn" luôn cuối, bất kể số lượng.
    if (a.domain === null || b.domain === null) {
      if (a.domain === null && b.domain === null) return 0
      return a.domain === null ? 1 : -1
    }
    if (b.entries.length !== a.entries.length) return b.entries.length - a.entries.length
    const byLatest = latest(b.notes).localeCompare(latest(a.notes))
    return byLatest !== 0 ? byLatest : a.label.localeCompare(b.label)
  })
}

export function groupSummary(notes: Note[]): string | null {
  const pieces = notes
    .slice(0, 2)
    .map((n) => (n.summary_text ?? n.content).replace(/\s+/g, ' ').trim())
    .filter(Boolean)
  if (pieces.length === 0) return null
  const text = pieces.join(' · ')
  return text.length > GROUP_SUMMARY_CHARS ? `${text.slice(0, GROUP_SUMMARY_CHARS - 1).trimEnd()}…` : text
}
