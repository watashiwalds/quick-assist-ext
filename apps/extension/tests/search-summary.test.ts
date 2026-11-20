/** Phase 5 — tổng hợp kết quả tìm kiếm: đếm theo `note_count`, không theo số note đã tải. */
import { describe, expect, it } from 'vitest'
import { countSearchNotes } from '../src/ui/features/search/searchSummary'

const source = (note_count: number, loaded: number) => ({
  domain: 'a.vn',
  label: 'a.vn',
  source_rank: 1,
  note_count,
  document_id: null,
  source_type: 'selection',
  notes: Array.from({ length: loaded }, (_, i) => ({
    note_id: `n${i}`,
    title: null,
    url: null,
    summary: null,
    snippet: 'x',
    score: 0.03,
    similarity: 0.6,
    part_index: 0,
    part_count: 1,
  })),
})

describe('countSearchNotes', () => {
  it('cộng note_count của mọi nguồn (kể cả note API chưa trả về)', () => {
    expect(countSearchNotes([source(12, 3), source(2, 2)])).toBe(14)
  })

  it('danh sách rỗng → 0', () => {
    expect(countSearchNotes([])).toBe(0)
  })
})
