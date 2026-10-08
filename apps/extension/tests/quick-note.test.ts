/**
 * N06 + N02 — outbox: hoàn tác, gửi lại khi mất mạng (backoff), lỗi không tự khắc phục chuyển
 * sang "failed" (KHÔNG mất ghi chú), Gửi lại / Bỏ, cắt vùng chọn quá dài, thư mục bị xoá → Inbox.
 */
import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppError } from '../src/shared/errors'
import { installChrome } from './helpers/chrome'

const { chrome } = installChrome()
const create = vi.fn()
vi.mock('../src/background/api', () => ({ api: { notes: { create: (...a: unknown[]) => create(...a) } } }))

const qn = await import('../src/background/notes/quick-note')
const { failedStore, notesCache, outbox, meta } = await import('../src/shared/storage/db')

const note = (id: string) => ({
  id, folder_id: 'inbox', url: null, domain: null, title: null, content: 'x', summary_text: null,
  index_status: 'PROCESSING' as const, version: 1, created_at: '2026-10-08T00:00:00Z', updated_at: '2026-10-08T00:00:00Z', deleted_at: null,
})

async function signIn() {
  await chrome.storage.local.set({ 'qa.refresh': 'rt' })
}
async function makeDue() {
  for (const i of await outbox.list()) await outbox.put({ ...i, notBefore: 0 })
}

beforeEach(async () => {
  vi.useRealTimers()
  create.mockReset()
  await notesCache.clear()
  await chrome.storage.local.clear()
  await signIn()
})

describe('ghi chú nhanh', () => {
  it('không có vùng chọn → báo lỗi, không tạo gì', async () => {
    expect(await qn.startQuickNote(1, { text: '   ' })).toBeNull()
    expect(await outbox.list()).toEqual([])
  })

  it('chưa đăng nhập → nhắc đăng nhập, không ghi outbox', async () => {
    await chrome.storage.local.clear()
    expect(await qn.startQuickNote(1, { text: 'abc' })).toBeNull()
    expect(await outbox.list()).toEqual([])
  })

  it('ghi outbox ngay, chưa gửi trong 5s; hoàn tác = không bao giờ gửi', async () => {
    const id = (await qn.startQuickNote(1, { text: 'Nội dung', url: 'https://a.vn/x', title: 'T' }))!
    expect((await outbox.get(id))!.body).toMatchObject({ content: 'Nội dung', url: 'https://a.vn/x', title: 'T' })
    await qn.flushOutbox()
    expect(create).not.toHaveBeenCalled() // còn trong cửa sổ hoàn tác
    expect(await qn.undoQuickNote(id)).toBe(true)
    await makeDue()
    await qn.flushOutbox()
    expect(create).not.toHaveBeenCalled()
    expect(await qn.undoQuickNote(id)).toBe(false) // đã hoàn tác/không còn
  })

  it('cắt vùng chọn > 20 000 ký tự và báo trên toast', async () => {
    const id = (await qn.startQuickNote(1, { text: 'a'.repeat(25_000) }))!
    expect((await outbox.get(id))!.body.content.length).toBe(20_000)
    const spec = chrome.scripting.executeScript.mock.calls.at(-1)![0].args[0]
    expect(spec.note).toMatch(/20.000/)
  })

  it('URL không phải http (chrome://, file://) không được gửi', async () => {
    const id = (await qn.startQuickNote(1, { text: 'x', url: 'chrome://settings' }))!
    expect((await outbox.get(id))!.body.url).toBeNull()
  })

  it('gửi thành công: dùng id outbox làm Idempotency-Key, cập nhật cache', async () => {
    const id = (await qn.startQuickNote(1, { text: 'x' }))!
    create.mockResolvedValue(note('n1'))
    await makeDue()
    await qn.flushOutbox()
    expect(create).toHaveBeenCalledWith(expect.objectContaining({ content: 'x' }), id)
    expect(await outbox.list()).toEqual([])
    expect((await notesCache.list()).map((n) => n.id)).toEqual(['n1'])
  })

  it('mất mạng → giữ trong outbox với backoff; lần sau gửi lại CÙNG key', async () => {
    const id = (await qn.startQuickNote(1, { text: 'x' }))!
    create.mockRejectedValueOnce(new AppError('NETWORK_ERROR', 'offline', 0))
    await makeDue()
    await qn.flushOutbox()
    const kept = (await outbox.get(id))!
    expect(kept.attempts).toBe(1)
    expect(kept.notBefore).toBeGreaterThan(Date.now() + 5_000)
    create.mockResolvedValue(note('n1'))
    await makeDue()
    await qn.flushOutbox()
    expect(create.mock.calls.map((c) => c[1])).toEqual([id, id])
  })

  it('lỗi không tự khắc phục (413) → chuyển "failed", hiện trong danh sách, Gửi lại được', async () => {
    const id = (await qn.startQuickNote(1, { text: 'x' }))!
    create.mockRejectedValueOnce(new AppError('NOTE_TOO_LONG', 'too long', 413))
    await makeDue()
    await qn.flushOutbox()
    expect(await outbox.list()).toEqual([])
    const pending = await qn.listPending()
    expect(pending).toMatchObject([{ id, state: 'failed', lastError: 'NOTE_TOO_LONG', snippet: 'x' }])
    create.mockResolvedValue(note('n1'))
    await qn.retryPending(id)
    expect(await qn.listPending()).toEqual([])
    expect(create).toHaveBeenCalledTimes(2)
  })

  it('hết phiên (401) → failed chờ đăng nhập lại; Bỏ = xoá vĩnh viễn', async () => {
    const id = (await qn.startQuickNote(1, { text: 'x' }))!
    create.mockRejectedValueOnce(new AppError('REFRESH_REUSED', 'x', 401))
    await makeDue()
    await qn.flushOutbox()
    expect((await failedStore.list()).map((i) => i.id)).toEqual([id])
    await qn.discardPending(id)
    expect(await qn.listPending()).toEqual([])
  })

  it('quá số lần thử với lỗi tạm thời → failed (không lặp vô hạn, không mất)', async () => {
    const id = (await qn.startQuickNote(1, { text: 'x' }))!
    await outbox.put({ ...(await outbox.get(id))!, attempts: qn.MAX_ATTEMPTS - 1, notBefore: 0 })
    create.mockRejectedValue(new AppError('HTTP_503', 'down', 503))
    await qn.flushOutbox()
    expect((await failedStore.list()).map((i) => i.lastError)).toEqual(['HTTP_503'])
  })

  it('thư mục đã bị xoá ở máy khác → gửi lại vào Inbox thay vì mất ghi chú', async () => {
    await meta.set('folders', JSON.stringify([{ id: 'f1', name: 'Học', is_default: false }]))
    const id = (await qn.startQuickNote(1, { text: 'x' }, 'f1'))!
    expect((await outbox.get(id))!.body.folder_id).toBe('f1')
    create.mockRejectedValueOnce(new AppError('FOLDER_NOT_FOUND', 'gone', 404)).mockResolvedValue(note('n1'))
    await makeDue()
    await qn.flushOutbox()
    await qn.flushOutbox()
    expect(create.mock.calls[1]![0]).not.toHaveProperty('folder_id')
    expect(await qn.listPending()).toEqual([])
  })

  it('thư mục mặc định trong Cài đặt được dùng khi không chọn', async () => {
    await meta.set('folders', JSON.stringify([{ id: 'f2', name: 'Đọc sau', is_default: false }]))
    await chrome.storage.local.set({ 'qa.prefs': { defaultFolderId: 'f2' } })
    const id = (await qn.startQuickNote(1, { text: 'x' }))!
    expect((await outbox.get(id))!.body.folder_id).toBe('f2')
    const spec = chrome.scripting.executeScript.mock.calls.at(-1)![0].args[0]
    expect(spec.folderName).toBe('Đọc sau')
  })

  it('backoff tăng dần, có trần 15 phút', () => {
    expect([0, 1, 2].map(qn.backoffMs)).toEqual([10_000, 20_000, 40_000])
    expect(qn.backoffMs(20)).toBe(15 * 60_000)
  })
})
