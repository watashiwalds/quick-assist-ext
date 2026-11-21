/** Phase 2 — gom ghi chú Thư viện theo nguồn; ADR-0018: chế độ 'page' (trang) / 'site' (domain). */
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

describe('groupNotesBySource — tài liệu nhiều part', () => {
  it('gom các part cùng document_id thành MỘT mục, nhãn là title part 0, part theo part_index', () => {
    const groups = groupNotesBySource([
      note('d1', { document_id: 'doc1', part_index: 1, part_count: 2, source_type: 'document', title: 'Bài báo dài' }),
      note('d0', { document_id: 'doc1', part_index: 0, part_count: 2, source_type: 'document', title: 'Bài báo dài' }),
      note('a1', { domain: 'a.vn' }),
    ])
    const doc = groups.find((g) => g.kind === 'document')!
    expect(doc.label).toBe('Bài báo dài')
    expect(doc.entries).toHaveLength(1)
    expect(doc.notes.map((n) => n.id)).toEqual(['d0', 'd1']) // sắp theo part_index
    expect(groups.find((g) => g.notes.some((n) => n.id === 'd0'))).toBe(doc)
  })

  it('tài liệu không URL vẫn có nhóm riêng, không trộn vào "Không rõ nguồn"', () => {
    const groups = groupNotesBySource([
      note('d0', { document_id: 'doc1', part_index: 0, part_count: 1, source_type: 'document', domain: null, url: null, title: 'Tài liệu không URL' }),
      note('u1', { domain: null, url: null }),
    ])
    expect(groups.map((g) => [g.kind, g.label])).toEqual([
      ['document', 'Tài liệu không URL'],
      ['site', UNKNOWN_SOURCE_LABEL],
    ])
  })

  it('tài liệu có URL → g.url là sourceKey để link "Mở trang nguồn"', () => {
    const groups = groupNotesBySource([
      note('d0', { document_id: 'doc1', part_index: 0, part_count: 1, source_type: 'document', url: 'https://a.vn/bai?utm=x', title: 'Tài liệu' }),
    ])
    expect(groups[0]!.url).toBe('https://a.vn/bai')
  })
})

describe('groupNotesBySource — chế độ site (mặc định cũ, theo domain)', () => {
  it('gom theo domain, nhóm nhiều note trước, trong nhóm mới nhất trước', () => {
    const groups = groupNotesBySource(
      [
        note('a1', { domain: 'a.vn', updated_at: '2026-10-01T00:00:00Z' }),
        note('b1', { domain: 'b.vn', updated_at: '2026-10-05T00:00:00Z' }),
        note('a2', { domain: 'a.vn', updated_at: '2026-10-03T00:00:00Z' }),
      ],
      'site',
    )
    expect(groups.map((g) => g.label)).toEqual(['a.vn', 'b.vn'])
    expect(groups[0]!.notes.map((n) => n.id)).toEqual(['a2', 'a1'])
  })

  it('note không có domain (hoặc rỗng) vào nhóm "Không rõ nguồn" và luôn cuối', () => {
    const groups = groupNotesBySource(
      [
        note('u1', { domain: null, url: null }),
        note('u2', { domain: '  ', url: null }),
        note('a1', { domain: 'a.vn' }),
        note('a2', { domain: 'a.vn' }),
      ],
      'site',
    )
    expect(groups.at(-1)).toMatchObject({ domain: null, label: UNKNOWN_SOURCE_LABEL, kind: 'site', url: null })
    expect(groups.at(-1)!.notes.map((n) => n.id).sort()).toEqual(['u1', 'u2'])
  })

  it('hai bài khác nhau cùng domain → MỘT nhóm site', () => {
    const groups = groupNotesBySource(
      [
        note('a1', { url: 'https://a.vn/bai-1', domain: 'a.vn' }),
        note('a2', { url: 'https://a.vn/bai-2', domain: 'a.vn' }),
      ],
      'site',
    )
    expect(groups).toHaveLength(1)
    expect(groups[0]!.label).toBe('a.vn')
    expect(groups[0]!.kind).toBe('site')
  })
})

describe('groupNotesBySource — chế độ page (ADR-0018, theo trang)', () => {
  it('hai bài khác path cùng domain → HAI nhóm trang, nhãn host + path', () => {
    const groups = groupNotesBySource([
      note('a1', { url: 'https://a.vn/bai-1?utm=x#top', domain: 'a.vn' }),
      note('a2', { url: 'https://a.vn/bai-2', domain: 'a.vn' }),
      note('a3', { url: 'https://a.vn/bai-1', domain: 'a.vn' }),
    ])
    expect(groups.map((g) => [g.label, g.kind])).toEqual([
      ['a.vn/bai-1', 'page'],
      ['a.vn/bai-2', 'page'],
    ])
    expect(groups[0]!.notes.map((n) => n.id).sort()).toEqual(['a1', 'a3'])
    expect(groups[0]!.url).toBeTruthy() // link "Mở trang nguồn"
    expect(groups[0]!.domain).toBe('a.vn')
  })

  it('URL chỉ khác query/hash → cùng một nhóm trang', () => {
    const groups = groupNotesBySource([
      note('a1', { url: 'https://a.vn/bai?utm=1' }),
      note('a2', { url: 'https://a.vn/bai?fbclid=2' }),
      note('a3', { url: 'https://a.vn/bai#x' }),
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0]!.notes).toHaveLength(3)
  })

  it('note không URL nhưng có domain → fallback nhóm site của domain đó', () => {
    const groups = groupNotesBySource([
      note('a1', { url: null, domain: 'a.vn' }),
      note('a2', { url: 'https://a.vn/bai-1' }),
    ])
    // Hai nhóm cùng domain, hoà số mục → tie-break theo nhãn ('a.vn' < 'a.vn/bai-1').
    expect(groups.map((g) => [g.label, g.kind, g.url])).toEqual([
      ['a.vn', 'site', null],
      ['a.vn/bai-1', 'page', 'https://a.vn/bai-1'],
    ])
  })

  it('note không URL không domain → "Không rõ nguồn" cuối', () => {
    const groups = groupNotesBySource([note('a1'), note('u1', { url: null, domain: null })])
    expect(groups.at(-1)).toMatchObject({ label: UNKNOWN_SOURCE_LABEL, kind: 'site', domain: null })
  })

  it('nhóm hoà số mục → lần cập nhật gần nhất trước; trang nhiều mục đứng trước', () => {
    const groups = groupNotesBySource([
      note('p1', { url: 'https://a.vn/bai-1', updated_at: '2026-09-01T00:00:00Z' }),
      note('p2', { url: 'https://a.vn/bai-1', updated_at: '2026-09-02T00:00:00Z' }),
      note('q1', { url: 'https://b.vn/mot-bai', updated_at: '2026-10-10T00:00:00Z' }),
    ])
    expect(groups.map((g) => g.label)).toEqual(['a.vn/bai-1', 'b.vn/mot-bai'])
  })
})

describe('groupNotesBySource — chung', () => {
  it('mặc định là chế độ page khi không truyền đối số', () => {
    const groups = groupNotesBySource([
      note('a1', { url: 'https://a.vn/bai-1' }),
      note('a2', { url: 'https://a.vn/bai-2' }),
    ])
    expect(groups).toHaveLength(2)
  })

  it('nhóm hoà số note → lần cập nhật gần nhất trước (site mode giữ hành vi cũ)', () => {
    const groups = groupNotesBySource(
      [
        note('old', { domain: 'old.vn', updated_at: '2026-09-01T00:00:00Z' }),
        note('new', { domain: 'new.vn', updated_at: '2026-10-10T00:00:00Z' }),
      ],
      'site',
    )
    expect(groups.map((g) => g.label)).toEqual(['new.vn', 'old.vn'])
  })

  it('danh sách rỗng → không nhóm', () => {
    expect(groupNotesBySource([])).toEqual([])
    expect(groupNotesBySource([], 'site')).toEqual([])
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
