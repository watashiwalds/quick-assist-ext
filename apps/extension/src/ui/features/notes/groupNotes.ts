/**
 * Gom ghi chú theo NGUỒN cho danh sách Thư viện (Phase 2 — UX plan §5.2).
 *
 * "nguồn" = `Note.domain` (hostname của URL; backend lấy khi tạo note). Ghi chú không có
 * domain vào nhóm "Không rõ nguồn", luôn xếp cuối. Nhóm xếp theo số ghi chú rồi lần cập nhật
 * gần nhất; trong nhóm xếp mới nhất trước. Hàm thuần, không I/O → unit test độc lập.
 */
import type { Note } from '@/shared/api/types'

export const UNKNOWN_SOURCE_LABEL = 'Không rõ nguồn'
const GROUP_SUMMARY_CHARS = 160

export interface NoteSourceGroup {
  domain: string | null
  label: string
  notes: Note[]
  /** Tóm tắt ghép từ tối đa 2 ghi chú (summary_text, fallback excerpt) — KHÔNG gọi AI. */
  summary: string | null
}

const latest = (notes: Note[]) => notes[0]?.updated_at ?? ''

export function groupNotesBySource(notes: Note[]): NoteSourceGroup[] {
  const buckets = new Map<string | null, Note[]>()
  for (const n of notes) {
    const domain = n.domain?.trim() || null
    const list = buckets.get(domain)
    if (list) list.push(n)
    else buckets.set(domain, [n])
  }

  const groups = [...buckets.entries()].map(([domain, list]) => {
    const sorted = [...list].sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    return {
      domain,
      label: domain ?? UNKNOWN_SOURCE_LABEL,
      notes: sorted,
      summary: groupSummary(sorted),
    }
  })

  return groups.sort((a, b) => {
    // "Không rõ nguồn" luôn cuối, bất kể số lượng.
    if (a.domain === null || b.domain === null) return a.domain === null ? (b.domain === null ? 0 : 1) : -1
    if (b.notes.length !== a.notes.length) return b.notes.length - a.notes.length
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
