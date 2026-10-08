/**
 * N07 — E2E ghi chú nhanh trên extension thật: vùng chọn → toast 5s → lưu lên server → index READY;
 * hoàn tác; mất mạng rồi gửi lại không trùng; hết quota (SKIPPED); trang đặc biệt; ô nhập liệu.
 */
import { expect, flushNow, openArticleAndSelect, PAGE, quickNoteViaShortcut, sql, test } from './fixtures'

test('lưu nhanh vùng bôi đen → toast → server lưu vào Inbox → READY', async ({ context, sw, api, panel: _p }) => {
  const { page, tabId, text } = await openArticleAndSelect(context, sw)
  const pendingId = await quickNoteViaShortcut(sw, tabId)
  expect(pendingId).toBeTruthy()
  await expect(page.locator('#quickassist-toast-host')).toBeAttached() // Shadow DOM đóng → chỉ kiểm host
  expect(await api.notes()).toHaveLength(0) // còn trong 5s hoàn tác
  const note = await api.waitForNote((n) => n.content === text.trim(), 15_000)
  expect(note).toMatchObject({ url: PAGE, title: 'Bài viết thử nghiệm QuickAssist', domain: '127.0.0.1' })
  const inbox = (await api.get('/folders'))[0]
  expect(note.folder_id).toBe(inbox.id)
  const ready = await api.waitForNote((n) => n.id === note.id && n.index_status === 'READY')
  expect(ready).toBeTruthy()
})

test('Hoàn tác bằng Alt+Shift+Z trong 5s → không có gì được lưu', async ({ context, sw, api, panel: _p }) => {
  const { page, tabId } = await openArticleAndSelect(context, sw, '#p2')
  await quickNoteViaShortcut(sw, tabId)
  await page.keyboard.press('Alt+Shift+z')
  await page.waitForTimeout(6_500)
  await flushNow(sw)
  expect(await api.notes()).toHaveLength(0)
})

test('mất mạng: ghi chú nằm trong outbox, có mạng lại thì gửi đúng 1 lần', async ({ context, sw, api, panel }) => {
  const { tabId, text } = await openArticleAndSelect(context, sw)
  await sw.evaluate(() => {
    ;(globalThis as any).__realFetch = fetch
    ;(globalThis as any).fetch = () => Promise.reject(new TypeError('Failed to fetch'))
  })
  await quickNoteViaShortcut(sw, tabId)
  await flushNow(sw) // thử gửi khi "offline" → giữ lại
  await panel.reload()
  await expect(panel.getByText(/đang chờ mạng để gửi lại/)).toBeVisible()
  expect(await api.notes()).toHaveLength(0)
  await sw.evaluate(() => {
    ;(globalThis as any).fetch = (globalThis as any).__realFetch
  })
  await flushNow(sw)
  await flushNow(sw) // gửi lại lần nữa cũng không tạo trùng (Idempotency-Key)
  const notes = await api.notes()
  expect(notes.filter((n) => n.content === text.trim())).toHaveLength(1)
})

test('hết quota AI: ghi chú vẫn được lưu nhưng SKIPPED, thư viện hiện trạng thái', async ({ context, sw, api, panel }) => {
  await api.get('/me/quota') // tạo tài khoản quota
  const me = await api.get('/me')
  await sql('UPDATE quota_accounts SET limit_tokens = 1 WHERE user_id = $1', [me.id])
  const { tabId } = await openArticleAndSelect(context, sw)
  await quickNoteViaShortcut(sw, tabId)
  await flushNow(sw)
  const skipped = await api.waitForNote((n) => n.index_status === 'SKIPPED')
  expect(skipped).toBeTruthy()
  await panel.reload()
  await expect(panel.getByText('Bỏ qua (hết quota)')).toBeVisible()
  await expect(panel.getByRole('button', { name: 'Thử lại AI' })).toBeVisible()
})

test('ô nhập liệu (textarea): lấy đúng phần bôi đen', async ({ context, sw, api, panel: _p }) => {
  const page = await context.newPage()
  await page.goto(PAGE)
  await page.evaluate(() => {
    const ta = document.querySelector('textarea')!
    ta.focus()
    ta.setSelectionRange(0, 22)
  })
  const tabId = await sw.evaluate(async (url) => (await chrome.tabs.query({ url }))[0]!.id!, PAGE)
  await quickNoteViaShortcut(sw, tabId)
  await flushNow(sw)
  expect((await api.notes()).map((n) => n.content)).toEqual(['Ghi chú trong ô nhập: '.trim()])
})

test('trang đặc biệt (chrome://) không cho tiêm script → không lỗi, không lưu gì', async ({ context, sw, api, panel: _p }) => {
  const page = await context.newPage()
  await page.goto('chrome://version')
  // Không có quyền "tabs" nên URL chrome:// bị ẩn → lấy tab mới nhất.
  const tabId = await sw.evaluate(async () => Math.max(...(await chrome.tabs.query({})).map((t) => t.id!)))
  expect(await quickNoteViaShortcut(sw, tabId)).toBeNull()
  expect(await api.notes()).toHaveLength(0)
  // service worker vẫn phản hồi
  expect(await sw.evaluate(() => typeof (globalThis as any).__qaE2E.flushOutbox)).toBe('function')
})

test('chọn thư mục khi lưu nhanh (C04): menu "Ghi chú vào thư mục"', async ({ context, sw, api, panel: _p }) => {
  const f = (await api.send('POST', '/folders', { name: 'Kubernetes' })).body
  await sw.evaluate(() => (globalThis as any).__qaE2E.dispatch('folders/list', undefined)) // làm mới menu
  const { tabId } = await openArticleAndSelect(context, sw)
  await quickNoteViaShortcut(sw, tabId, f.id)
  await flushNow(sw)
  const n = await api.waitForNote(() => true)
  expect(n.folder_id).toBe(f.id)
})
