/** C02 (đồng bộ tăng dần, tombstone, single-flight) + A03 (phiên: refresh single-flight, hết phiên). */
import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { installChrome } from './helpers/chrome'

const { chrome } = installChrome()
const list = vi.fn()
vi.mock('../src/background/api', () => ({ api: { notes: { list: (...a: unknown[]) => list(...a) } } }))
const refresh = vi.fn()
vi.mock('../src/shared/api/endpoints', () => ({ createApi: () => ({ auth: { refresh: (...a: unknown[]) => refresh(...a), logout: vi.fn() } }) }))

const { syncNotes, LAST_SYNC } = await import('../src/background/notes/sync')
const session = await import('../src/background/auth/session')
const { meta, notesCache } = await import('../src/shared/storage/db')

const n = (id: string, updated_at: string, deleted_at: string | null = null) => ({
  id, folder_id: 'f', url: null, domain: null, title: null, content: id, summary_text: null,
  index_status: 'READY' as const, version: 1, created_at: updated_at, updated_at, deleted_at,
})

describe('đồng bộ tăng dần (C02)', () => {
  beforeEach(async () => {
    list.mockReset()
    await notesCache.clear()
  })

  it('lần đầu tải hết theo cursor, lưu mốc updated_at lớn nhất (so sánh theo thời gian)', async () => {
    list
      .mockResolvedValueOnce({ items: [n('a', '2026-10-08T10:00:00.5Z')], next_cursor: 'c1' })
      .mockResolvedValueOnce({ items: [n('b', '2026-10-08T10:00:01Z')], next_cursor: null })
    expect(await syncNotes()).toBe(2)
    expect(list.mock.calls[0]![0]).toMatchObject({ updated_since: undefined })
    expect(list.mock.calls[1]![0]).toMatchObject({ cursor: 'c1' })
    expect(await meta.get(LAST_SYNC)).toBe('2026-10-08T10:00:01Z')
    expect((await notesCache.list()).map((x) => x.id)).toEqual(['b', 'a'])
  })

  it('lần sau gửi updated_since; tombstone xoá note khỏi cache (xoá ở máy khác)', async () => {
    await meta.set(LAST_SYNC, '2026-10-08T10:00:01Z')
    await notesCache.apply([n('a', '2026-10-08T10:00:00Z')])
    list.mockResolvedValueOnce({ items: [n('a', '2026-10-08T11:00:00Z', '2026-10-08T11:00:00Z')], next_cursor: null })
    await syncNotes()
    expect(list.mock.calls[0]![0]).toMatchObject({ updated_since: '2026-10-08T10:00:01Z' })
    expect(await notesCache.list()).toEqual([])
  })

  it('nhiều màn hình gọi cùng lúc → chỉ MỘT lượt đồng bộ', async () => {
    list.mockResolvedValue({ items: [], next_cursor: null })
    await Promise.all([syncNotes(), syncNotes(), syncNotes()])
    expect(list).toHaveBeenCalledTimes(1)
  })
})

describe('phiên đăng nhập (A03)', () => {
  beforeEach(async () => {
    refresh.mockReset()
    await chrome.storage.local.clear()
    await chrome.storage.session.clear()
  })

  it('access token còn hạn → dùng luôn, không refresh', async () => {
    await session.saveTokens({ access_token: 'A', refresh_token: 'R', expires_in: 900, token_type: 'Bearer', is_new_user: false })
    expect(await session.getAccessToken()).toBe('A')
    expect(refresh).not.toHaveBeenCalled()
    // access ở storage.session (mất khi đóng trình duyệt), refresh ở storage.local
    expect(chrome.storage.session._dump()['qa.access']).toMatchObject({ token: 'A' })
    expect(chrome.storage.local._dump()['qa.refresh']).toBe('R')
  })

  it('nhiều request cùng gặp hết hạn → refresh đúng MỘT lần (tránh REFRESH_REUSED)', async () => {
    await session.saveTokens({ access_token: 'A', refresh_token: 'R', expires_in: 1, token_type: 'Bearer', is_new_user: false })
    refresh.mockImplementation(async () => {
      await new Promise((r) => setTimeout(r, 20))
      return { access_token: 'A2', refresh_token: 'R2', expires_in: 900, token_type: 'Bearer', is_new_user: false }
    })
    const tokens = await Promise.all([session.getAccessToken(), session.getAccessToken(), session.getAccessToken()])
    expect(tokens).toEqual(['A2', 'A2', 'A2'])
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(refresh).toHaveBeenCalledWith('R')
  })

  it('refresh thất bại → xoá token, coi như đăng xuất', async () => {
    await session.saveTokens({ access_token: 'A', refresh_token: 'R', expires_in: 1, token_type: 'Bearer', is_new_user: false })
    refresh.mockRejectedValue(new Error('REFRESH_REUSED'))
    expect(await session.getAccessToken()).toBeNull()
    expect(await session.hasSession()).toBe(false)
  })
})
