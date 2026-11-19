/** Phase 5 — nhóm nguồn chat là hàm thuần: test trực tiếp thay vì chỉ qua UI ChatView. */
import { describe, expect, it } from 'vitest'
import type { ChatSource } from '../src/shared/api/types'
import { groupChatSources } from '../src/ui/features/chat/Sources'

const source = (over: Partial<ChatSource> & Pick<ChatSource, 'index' | 'note_id'>): ChatSource => ({
  source_index: 1,
  source_domain: 'a.example',
  chunk_id: `c-${over.index}`,
  title: `Ghi chú ${over.index}`,
  url: null,
  snippet: 'đoạn trích',
  ...over,
})

describe('groupChatSources', () => {
  it('nhóm theo source_index, giữ thứ tự trích dẫn và đặt "Không rõ nguồn" cuối', () => {
    const groups = groupChatSources([
      source({ index: 1, note_id: 'n1', source_index: 1, source_domain: 'a.example' }),
      source({ index: 2, note_id: 'n2', source_index: 2, source_domain: 'b.example' }),
      source({ index: 3, note_id: 'n1', source_index: 1, source_domain: 'a.example' }),
      source({ index: 4, note_id: 'n3', source_index: 3, source_domain: null }),
    ])
    expect(groups.map((g) => g.label)).toEqual(['a.example', 'b.example', 'Không rõ nguồn'])
    expect(groups[0]!.notes.map((s) => s.index)).toEqual([1, 3])
    expect(groups.at(-1)!.domain).toBeNull()
  })

  it('cùng domain nhưng source_index khác → không gộp (backend gắn một index/nguồn)', () => {
    const groups = groupChatSources([
      source({ index: 1, note_id: 'n1', source_index: 1, source_domain: 'a.example' }),
      source({ index: 2, note_id: 'n2', source_index: 2, source_domain: 'a.example' }),
    ])
    expect(groups).toHaveLength(2)
    expect(groups.map((g) => g.key)).toEqual(['r1', 'r2'])
  })

  it('hội thoại cũ chưa có source_index → nhóm theo source_domain, không crash', () => {
    const legacy = (over: Partial<ChatSource> & Pick<ChatSource, 'index' | 'note_id'>) => {
      const s = source(over)
      delete (s as Partial<ChatSource>).source_index
      delete (s as Partial<ChatSource>).source_domain
      return { ...s, ...(over.source_domain !== undefined ? { source_domain: over.source_domain } : {}) } as ChatSource
    }
    const groups = groupChatSources([
      legacy({ index: 1, note_id: 'n1', source_domain: 'a.example' }),
      legacy({ index: 2, note_id: 'n2', source_domain: 'a.example' }),
      legacy({ index: 3, note_id: 'n3' }),
    ])
    expect(groups.map((g) => g.label)).toEqual(['a.example', 'Không rõ nguồn'])
    expect(groups[0]!.notes).toHaveLength(2)
  })

  it('rỗng → không nhóm', () => {
    expect(groupChatSources([])).toEqual([])
  })
})
