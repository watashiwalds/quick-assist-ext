import 'fake-indexeddb/auto'
import { describe, expect, it } from 'vitest'
import { notesCache, outbox } from '../src/shared/storage/db'

describe('outbox & cache', () => {
  it('chỉ trả mục đã hết cửa sổ hoàn tác; hoàn tác = xoá', async () => {
    const now = Date.now()
    await outbox.put({ id: 'a', body: { content: 'x' }, notBefore: now - 1, attempts: 0, createdAt: now })
    await outbox.put({ id: 'b', body: { content: 'y' }, notBefore: now + 5000, attempts: 0, createdAt: now })
    expect((await outbox.due(now)).map((i) => i.id)).toEqual(['a'])
    expect(await outbox.remove('b')).toBe(true)
    expect(await outbox.remove('b')).toBe(false)
  })

  it('tombstone từ sync xoá note khỏi cache', async () => {
    const base = {
      folder_id: 'f', url: null, domain: null, title: null, content: 'c', summary_text: null,
      index_status: 'READY' as const, version: 1, created_at: '2026-01-01', updated_at: '2026-01-01',
    }
    await notesCache.apply([{ ...base, id: 'n1', deleted_at: null }])
    expect((await notesCache.list()).length).toBe(1)
    await notesCache.apply([{ ...base, id: 'n1', deleted_at: '2026-01-02' }])
    expect(await notesCache.list()).toEqual([])
  })
})
