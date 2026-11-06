/** SUM-03/SUM-04 (UI) + A08 — tóm tắt ghi chú & vùng chọn, cài đặt, xoá tài khoản xoá cả dữ liệu máy. */
import { expect, openArticleAndSelect, test } from './fixtures'

test('tóm tắt ghi chú: xem trước → Lưu → hiện "Tóm tắt đã lưu"', async ({ panel, api }) => {
  const n = (await api.send('POST', '/notes', { content: 'Đoạn văn dài về pgvector và chỉ mục HNSW.', title: 'pgvector' })).body
  await panel.reload()
  await panel.getByRole('button', { name: 'Tóm tắt bằng AI' }).click()
  await expect(panel.getByText('Bản xem trước — chưa lưu')).toBeVisible()
  expect((await api.get(`/notes/${n.id}`)).summary_text).toBeNull() // preview không ghi DB
  await panel.getByRole('button', { name: 'Lưu tóm tắt' }).click()
  await expect(panel.getByText('Tóm tắt đã lưu')).toBeVisible()
  expect((await api.get(`/notes/${n.id}`)).summary_text).toBeTruthy()
})

test('tóm tắt vùng chọn từ menu chuột phải → tab Tóm tắt → Lưu thành ghi chú', async ({ context, sw, panel, api }) => {
  const { tabId: _t } = await openArticleAndSelect(context, sw, '#p2')
  await sw.evaluate(async () => {
    const qa = (globalThis as any).__qaE2E
    const [tab] = await chrome.tabs.query({ url: 'http://127.0.0.1:4173/article.html' })
    const sel = await qa.getSelection(tab!.id)
    await qa.setPendingSelection({ ...sel })
    chrome.runtime.sendMessage({ channel: 'qa-event', type: 'selection/pending' }).catch(() => undefined)
  })
  await panel.bringToFront() // panel đang mở nhận sự kiện 'selection/pending' và tự chuyển tab
  await expect(panel.getByRole('tab', { name: 'Tóm tắt' })).toHaveAttribute('aria-selected', 'true')
  await expect(panel.getByText('Bản xem trước — chưa lưu')).toBeVisible()
  await panel.getByRole('button', { name: 'Lưu thành ghi chú' }).click()
  const note = await api.waitForNote((x: any) => !!x.summary_text)
  expect(note.content).toContain('Service cung cấp địa chỉ ổn định')
})

test('cài đặt: hạn mức, thư mục mặc định; xoá tài khoản 2 bước xoá dữ liệu server + máy', async ({ panel, api, sw }) => {
  await api.send('POST', '/notes', { content: 'sẽ bị xoá' })
  const f = (await api.send('POST', '/folders', { name: 'Mặc định mới' })).body
  await panel.reload()
  await panel.getByRole('tab', { name: 'Cài đặt' }).click()
  await expect(panel.getByText(/còn lại/)).toBeVisible()
  await panel.getByLabel(/Thư mục mặc định/).selectOption(f.id)
  await expect(panel.getByText('Đã lưu thư mục mặc định')).toBeVisible()
  await panel.getByRole('button', { name: 'Xoá tài khoản…' }).click()
  await panel.getByRole('button', { name: 'Tiếp tục' }).click()
  await panel.getByLabel(/Gõ “XOÁ”/).fill('XOÁ')
  await panel.getByRole('button', { name: 'Xoá vĩnh viễn' }).click()
  await expect(panel.getByRole('button', { name: 'Đăng nhập bằng Google' })).toBeVisible()
  expect((await api.send('GET', '/me')).status).toBe(404)
  const local = await sw.evaluate(async () => ({
    storage: await chrome.storage.local.get(null),
    notes: await new Promise<number>((ok) => {
      const r = indexedDB.open('quickassist')
      r.onsuccess = () => {
        const c = r.result.transaction('notes').objectStore('notes').count()
        c.onsuccess = () => ok(c.result)
      }
    }),
  }))
  expect(local.notes).toBe(0)
  expect(Object.keys(local.storage)).not.toContain('qa.refresh')
  expect(Object.keys(local.storage)).not.toContain('qa.prefs')
})
