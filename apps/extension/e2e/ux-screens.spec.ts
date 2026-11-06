/**
 * P04 — chụp màn hình THẬT của extension cho tài liệu UX (docs/ux/screens). Không chạy trong CI.
 *   UX_SCREENS=1 npx playwright test e2e/ux-screens.spec.ts
 */
import { join } from 'node:path'
import { expect, flushNow, openArticleAndSelect, quickNoteViaShortcut, sql, test } from './fixtures'

const OUT = join(import.meta.dirname, '..', '..', '..', 'docs', 'ux', 'screens')
test.skip(!process.env.UX_SCREENS, 'chỉ chạy khi UX_SCREENS=1')
test.use({ viewport: { width: 400, height: 720 } })

test('chụp các màn chính', async ({ context, sw, panel, api, extId }) => {
  const shot = (name: string, page = panel) => page.screenshot({ path: join(OUT, `${name}.png`) })
  await panel.setViewportSize({ width: 400, height: 720 })

  // 01 popup chưa đăng nhập (profile mới)
  const pop = await context.newPage()
  await pop.setViewportSize({ width: 340, height: 300 })
  await pop.goto(`chrome-extension://${extId}/src/ui/popup/index.html`)
  await pop.waitForTimeout(400)
  await shot('01-popup', pop)
  await pop.close()

  // 02 thư viện trống
  await shot('02-thu-vien-trong')

  // dữ liệu mẫu
  const f = (await api.send('POST', '/folders', { name: 'Học tập' })).body
  await api.send('POST', '/notes', { title: 'Phở bò Hà Nội', content: 'Hầm xương bò khoảng 8 tiếng, gia vị quế hồi thảo quả rang thơm. Bánh phở tươi trụng nhanh.', url: 'https://amthuc.example/pho' })
  await api.send('POST', '/notes', { title: 'Kubernetes Deployment', content: 'Deployment quản lý ReplicaSet và hỗ trợ rolling update không gián đoạn dịch vụ.', url: 'https://docs.example/k8s', folder_id: f.id })
  await api.waitForNote((n) => n.title === 'Kubernetes Deployment' && n.index_status === 'READY')
  const failed = (await api.send('POST', '/notes', { title: 'Ghi chú lỗi AI (minh hoạ)', content: 'Ghi chú này minh hoạ trạng thái lỗi xử lý AI.' })).body
  await api.waitForNote((n) => n.id === failed.id && n.index_status === 'READY')
  await sql("UPDATE notes SET index_status = 'FAILED' WHERE id = $1", [failed.id])
  // 1 ghi chú chưa gửi được (outbox failed)
  await sw.evaluate(async () => {
    const d = await new Promise<IDBDatabase>((ok) => {
      const r = indexedDB.open('quickassist')
      r.onsuccess = () => ok(r.result)
    })
    const tx = d.transaction('failed', 'readwrite')
    tx.objectStore('failed').put({ id: 'demo', body: { content: 'Đoạn trích rất dài từ trang tài liệu…' }, notBefore: 0, attempts: 3, lastError: 'NOTE_TOO_LONG', createdAt: Date.now(), failedAt: Date.now() })
    await new Promise((ok) => (tx.oncomplete = ok))
  })
  await panel.reload()
  await expect(panel.getByRole('heading', { name: 'Phở bò Hà Nội' })).toBeVisible()
  await shot('03-thu-vien')
  await panel.getByRole('button', { name: 'Xem' }).click()
  await shot('04-ghi-chu-chua-gui')
  await panel.getByRole('button', { name: 'Ẩn' }).click()

  await panel.getByRole('listitem', { name: 'Phở bò Hà Nội' }).getByRole('button', { name: 'Sửa' }).click()
  await shot('05-sua-ghi-chu')
  const pho = (await api.notes()).find((n) => n.title === 'Phở bò Hà Nội')
  await panel.getByLabel('Nội dung').fill('Bản tôi sửa trên máy này.')
  await api.send('PATCH', `/notes/${pho.id}`, { version: pho.version, title: 'Phở bò (máy khác sửa)' })
  await panel.getByRole('button', { name: 'Lưu' }).click()
  await expect(panel.getByText(/đã được sửa ở nơi khác/)).toBeVisible()
  await shot('06-xung-dot-409')
  await panel.keyboard.press('Escape')

  await panel.getByRole('button', { name: 'Thư mục', exact: true }).click()
  await shot('07-quan-ly-thu-muc')
  await panel.keyboard.press('Escape')

  await panel.getByRole('button', { name: 'Chọn', exact: true }).click()
  await panel.getByLabel(/Chọn “Kubernetes/).check()
  await shot('08-chon-nhieu')
  await panel.getByRole('button', { name: 'Xong' }).click()

  await panel.getByRole('listitem', { name: 'Kubernetes Deployment' }).getByRole('button', { name: 'Tóm tắt bằng AI' }).click()
  await expect(panel.getByText('Bản xem trước — chưa lưu')).toBeVisible()
  await shot('09-tom-tat-xem-truoc')

  await panel.getByRole('tab', { name: 'Tìm kiếm' }).click()
  await panel.getByLabel('Câu hỏi tìm kiếm').fill('ham xuong bo bao lau')
  await panel.getByRole('button', { name: 'Tìm', exact: true }).click()
  await expect(panel.locator('ol.list > li').first()).toBeVisible()
  await shot('10-tim-kiem')
  await panel.getByLabel('Câu hỏi tìm kiếm').fill('tên lửa vũ trụ sao hoả')
  await panel.getByLabel('Tìm trong thư mục').selectOption(f.id)
  await panel.getByRole('button', { name: 'Tìm', exact: true }).click()
  await shot('11-tim-kiem-khong-co-ket-qua')

  // tóm tắt vùng chọn
  const first = await openArticleAndSelect(context, sw, '#p2')
  await sw.evaluate(async (tabId) => {
    const qa = (globalThis as any).__qaE2E
    await qa.setPendingSelection(await qa.getSelection(tabId))
    chrome.runtime.sendMessage({ channel: 'qa-event', type: 'selection/pending' }).catch(() => undefined)
  }, first.tabId)
  await panel.bringToFront()
  await expect(panel.getByText('Bản xem trước — chưa lưu')).toBeVisible()
  await shot('12-tom-tat-vung-chon')
  await first.page.close()

  // toast trên trang
  const { page, tabId } = await openArticleAndSelect(context, sw, '#p1')
  await page.setViewportSize({ width: 900, height: 420 })
  await quickNoteViaShortcut(sw, tabId)
  await page.waitForTimeout(600)
  await shot('13-toast-tren-trang', page)
  await page.keyboard.press('Alt+Shift+z')
  await page.waitForTimeout(400)
  await shot('14-toast-hoan-tac', page)
  await flushNow(sw)

  // cài đặt gần hết quota + hết quota ở tìm kiếm
  const me = await api.get('/me')
  await sql('UPDATE quota_accounts SET limit_tokens = used_tokens + 40 WHERE user_id = $1', [me.id])
  await panel.bringToFront()
  await panel.getByRole('tab', { name: 'Cài đặt' }).click()
  await expect(panel.getByText(/còn lại/)).toBeVisible()
  await shot('15-cai-dat')
  await panel.getByRole('button', { name: 'Xoá tài khoản…' }).click()
  await panel.getByRole('button', { name: 'Tiếp tục' }).click()
  await shot('16-xoa-tai-khoan-buoc-2')
  await panel.keyboard.press('Escape')
  await sql('UPDATE quota_accounts SET limit_tokens = 0 WHERE user_id = $1', [me.id])
  await panel.getByRole('tab', { name: 'Tìm kiếm' }).click()
  await panel.getByLabel('Câu hỏi tìm kiếm').fill('phở')
  await panel.getByRole('button', { name: 'Tìm', exact: true }).click()
  await expect(panel.getByText(/hết hạn mức AI/)).toBeVisible()
  await shot('17-het-quota')
})
