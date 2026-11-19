/**
 * C05 — thư viện trên extension thật: cache-first + offline, sửa có xung đột version (409),
 * xoá một/nhiều, quản lý thư mục (xoá → note về Inbox), xoá ở "máy khác" biến mất sau sync.
 */
import { expect, test } from './fixtures'

async function seed(api: any, n: number, folderId?: string) {
  const out = []
  for (let i = 0; i < n; i++) {
    out.push((await api.send('POST', '/notes', { content: `Ghi chú số ${i} về pgvector`, title: `Note ${i}`, ...(folderId ? { folder_id: folderId } : {}) })).body)
  }
  return out
}

test('mở thư viện: hiện ghi chú từ server; mất mạng vẫn mở được từ cache', async ({ panel, api, sw }) => {
  await seed(api, 3)
  await panel.reload()
  await expect(panel.getByRole('heading', { name: 'Note 2' })).toBeVisible()
  await sw.evaluate(() => {
    ;(globalThis as any).fetch = () => Promise.reject(new TypeError('Failed to fetch'))
  })
  await panel.reload()
  const t0 = Date.now()
  await expect(panel.getByRole('heading', { name: 'Note 0' })).toBeVisible()
  expect(Date.now() - t0).toBeLessThan(2000) // cache-first (NFR < 200 ms đo trong render, ở đây có reload trang)
})

test('sửa ghi chú; xung đột 409 khi máy khác đã sửa → ghi đè theo lựa chọn', async ({ panel, api }) => {
  const [n] = await seed(api, 1)
  await panel.reload()
  // mở ghi chú trong reader rồi bấm Sửa (editor nhúng thay modal — W03)
  await panel.locator('.note-list').getByRole('heading', { name: 'Note 0' }).click()
  await panel.getByRole('button', { name: 'Sửa' }).click()
  await panel.getByLabel('Nội dung').fill('Nội dung tôi sửa')
  // "máy khác" sửa trước
  await api.send('PATCH', `/notes/${n.id}`, { version: 1, title: 'Máy khác' })
  await panel.getByRole('button', { name: 'Lưu' }).click()
  await expect(panel.getByText(/đã được sửa ở nơi khác/)).toBeVisible()
  await panel.getByRole('button', { name: /Ghi đè/ }).click()
  await expect(panel.getByText('Đã ghi đè bằng bản của bạn')).toBeVisible()
  await expect(panel.getByRole('dialog')).toHaveCount(0)
  await expect.poll(async () => (await api.get(`/notes/${n.id}`)).content).toBe('Nội dung tôi sửa')
  expect(await api.get(`/notes/${n.id}`)).toMatchObject({ title: 'Note 0', version: 3 }) // tiêu đề máy khác bị ghi đè theo lựa chọn
})

test('xoá một và xoá nhiều ghi chú có xác nhận', async ({ panel, api }) => {
  await seed(api, 4)
  await panel.reload()
  await panel.locator('.note-list').getByRole('heading', { name: 'Note 3' }).click()
  await panel.getByRole('button', { name: 'Xoá' }).click() // footer của reader
  await panel.getByRole('dialog').getByRole('button', { name: 'Xoá' }).click()
  await expect(panel.getByRole('heading', { name: 'Note 3' })).toHaveCount(0) // khỏi danh sách lẫn reader (đã đóng)
  await panel.getByRole('button', { name: 'Chọn', exact: true }).click()
  await panel.getByLabel('Chọn “Note 0”').check()
  await panel.getByLabel('Chọn “Note 1”').check()
  await panel.getByRole('button', { name: 'Xoá (2)' }).click()
  await panel.getByRole('dialog').getByRole('button', { name: 'Xoá' }).click()
  await expect(panel.getByText('Đã xoá 2 ghi chú')).toBeVisible()
  expect((await api.notes()).map((x: any) => x.title)).toEqual(['Note 2'])
})

test('nhóm theo nguồn + chuyển nhiều ghi chú đã chọn sang thư mục khác', async ({ panel, api }) => {
  await api.send('POST', '/notes', { content: 'nội dung A', title: 'A', url: 'https://same.example/a' })
  await api.send('POST', '/notes', { content: 'nội dung B', title: 'B', url: 'https://same.example/b' })
  await api.send('POST', '/notes', { content: 'nội dung C', title: 'C' })
  const f = (await api.send('POST', '/folders', { name: 'Đích' })).body
  await panel.reload()

  // cùng domain → cùng nhóm; note không URL → "Không rõ nguồn"
  const group = panel.getByRole('region', { name: 'Nguồn same.example' })
  await expect(group.getByRole('heading', { name: 'A' })).toBeVisible()
  await expect(group.getByRole('heading', { name: 'B' })).toBeVisible()
  await expect(panel.getByRole('region', { name: 'Nguồn Không rõ nguồn' })).toBeVisible()

  // chọn 2 note trong nhóm rồi chuyển; note C không bị chuyển
  await panel.getByRole('button', { name: 'Chọn', exact: true }).click()
  await panel.getByLabel('Chọn “A”').check()
  await panel.getByLabel('Chọn “B”').check()
  await panel.getByRole('button', { name: 'Chuyển thư mục' }).click()
  const dlg = panel.getByRole('dialog')
  await dlg.getByLabel('Thư mục đích').selectOption(f.id)
  await dlg.getByRole('button', { name: 'Chuyển (2)' }).click()
  await expect(panel.getByText('Đã chuyển 2 ghi chú')).toBeVisible()
  await expect.poll(async () => (await api.get(`/notes?folder_id=${f.id}`)).items.map((x: any) => x.title)).toEqual(['A', 'B'])
  await expect(panel.getByRole('heading', { name: 'A' })).toHaveCount(0)
  await expect(panel.getByRole('heading', { name: 'C' })).toBeVisible()
})

test('quản lý thư mục: tạo, đổi tên, xoá → ghi chú về Inbox', async ({ panel, api }) => {
  await panel.getByRole('button', { name: 'Thư mục', exact: true }).click()
  const dlg = panel.getByRole('dialog')
  await dlg.getByLabel('Tên thư mục mới').fill('Đọc sau')
  await dlg.getByRole('button', { name: 'Tạo' }).click()
  await expect(dlg.getByText('Đọc sau')).toBeVisible()
  await dlg.getByLabel('Tên thư mục mới').fill('Đọc sau')
  await dlg.getByRole('button', { name: 'Tạo' }).click()
  await expect(dlg.getByText('Đã có thư mục cùng tên.')).toBeVisible()
  await dlg.getByRole('button', { name: 'Đổi tên' }).click()
  await dlg.getByLabel('Tên mới cho Đọc sau').fill('Đọc cuối tuần')
  await dlg.getByRole('button', { name: 'Lưu' }).click()
  await expect(dlg.getByText('Đọc cuối tuần')).toBeVisible()
  const folder = (await api.get('/folders')).find((f: any) => f.name === 'Đọc cuối tuần')
  await seed(api, 2, folder.id)
  await dlg.getByRole('button', { name: 'Xoá' }).click()
  await panel.getByRole('dialog', { name: /Xoá thư mục/ }).getByRole('button', { name: 'Xoá thư mục' }).click()
  await expect(panel.getByText('Đã xoá thư mục, ghi chú đã về Inbox')).toBeVisible()
  const inbox = (await api.get('/folders'))[0]
  expect((await api.notes()).every((n: any) => n.folder_id === inbox.id)).toBe(true)
})

test('ghi chú bị xoá ở máy khác biến mất khỏi thư viện sau đồng bộ (tombstone)', async ({ panel, api }) => {
  const [a] = await seed(api, 2)
  await panel.reload()
  await expect(panel.getByRole('heading', { name: 'Note 0' })).toBeVisible()
  await api.send('DELETE', `/notes/${a.id}`)
  await panel.getByRole('button', { name: 'Đồng bộ' }).click()
  await expect(panel.getByRole('heading', { name: 'Note 0' })).toHaveCount(0)
  await expect(panel.getByRole('heading', { name: 'Note 1' })).toBeVisible()
})
