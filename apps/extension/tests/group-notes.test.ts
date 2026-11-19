/** Phase 2 — gom ghi chú Thư viện theo nguồn (domain), summary-first, nhóm không rõ nguồn cuối. */
import { describe, expect, it } from 'vitest'
import type { Note } from '../src/shared/api/types'
import { groupNotesBySource, groupSummary, UNKNOWN_SOURCE_LABEL } from '../src/ui/features/notes/groupNotes'

const note = (id: string, over: Partial<Note> = {}) =>
  ({
    id,
    folder_id: 'inbox',
    url: 'https://a.vn/x',
    domain: 'a.vn',
    title: id,
    content: `Nội dung ${id}`,
    summary_text: null,
    index_status: 'READY',
    version: 1,
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
    deleted_at: null,
    ...over,
  }) as Note

describe('groupNotesBySource', () => {
  it('gom theo domain, nhóm nhiều note trước, trong nhóm mới nhất trước', () => {
    const groups = groupNotesBySource([
      note('a1', { domain: 'a.vn', updated_at: '2026-10-01T00:00:00Z' }),
      note('b1', { domain: 'b.vn', updated_at: '2026-10-05T00:00:00Z' }),
      note('a2', { domain: 'a.vn', updated_at: '2026-10-03T00:00:00Z' }),
    ])
    expect(groups.map((g) => g.label)).toEqual(['a.vn', 'b.vn'])
    expect(groups[0]!.notes.map((n) => n.id)).toEqual(['a2', 'a1'])
  })

  it('note không có domain (hoặc rỗng) vào nhóm "Không rõ nguồn" và luôn cuối', () => {
    const groups = groupNotesBySource([
      note('u1', { domain: null, url: null }),
      note('u2', { domain: '  ', url: null }),
      note('a1', { domain: 'a.vn' }),
      note('a2', { domain: 'a.vn' }),
    ])
    expect(groups.at(-1)).toMatchObject({ domain: null, label: UNKNOWN_SOURCE_LABEL })
    expect(groups.at(-1)!.notes.map((n) => n.id).sort()).toEqual(['u1', 'u2'])
  })

  it('nhóm hoà số note → lần cập nhật gần nhất trước', () => {
    const groups = groupNotesBySource([
      note('old', { domain: 'old.vn', updated_at: '2026-09-01T00:00:00Z' }),
      note('new', { domain: 'new.vn', updated_at: '2026-10-10T00:00:00Z' }),
    ])
    expect(groups.map((g) => g.label)).toEqual(['new.vn', 'old.vn'])
  })

  it('danh sách rỗng → không nhóm', () => {
    expect(groupNotesBySource([])).toEqual([])
  })
})

describe('groupSummary', () => {
  it('ưu tiên summary_text, ghép tối đa 2 ghi chú, chuẩn hoá khoảng trắng', () => {
    expect(groupSummary([
      note('a', { summary_text: '  tóm tắt A \n' }),
      note('b', { content: 'nội dung\n B' }),
      note('c', { summary_text: 'không dùng' }),
    ])).toBe('tóm tắt A · nội dung B')
  })

  it('cắt ngắn khi vượt 160 ký tự', () => {
    const out = groupSummary([note('a', { content: 'x'.repeat(300) })])
    expect(out).toHaveLength(160)
    expect(out!.endsWith('…')).toBe(true)
  })

  it('không có nội dung → null', () => {
    expect(groupSummary([note('a', { content: '', summary_text: null })])).toBeNull()
  })
})
