/** H05 — accessibility: quét axe-core (WCAG 2.1 A/AA) mọi màn chính + điều hướng chỉ bằng bàn phím. */
import AxeBuilder from '@axe-core/playwright'
import { expect, test } from './fixtures'

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

for (const tab of ['Thư viện', 'Tìm trong trang', 'Hỏi AI', 'Cài đặt']) {
  test(`axe: màn "${tab}" không có vi phạm WCAG AA`, async ({ panel, api }) => {
    await api.send('POST', '/notes', { content: 'Ghi chú mẫu để có nội dung', title: 'Mẫu', url: 'https://a.example/x' })
    await panel.reload()
    await panel.getByRole('tab', { name: tab }).click()
    await panel.waitForTimeout(500)
    const r = await new AxeBuilder({ page: panel }).withTags(TAGS).analyze()
    expect(r.violations.map((v) => `${v.id}: ${v.nodes.length} — ${v.help}`)).toEqual([])
  })
}

test('axe: màn sửa ghi chú (editor nhúng trong reader)', async ({ panel, api }) => {
  await api.send('POST', '/notes', { content: 'abc', title: 'Mẫu' })
  await panel.reload()
  await panel.locator('.note-list').getByRole('heading', { name: 'Mẫu' }).click()
  await panel.getByRole('button', { name: 'Sửa' }).click()
  const r = await new AxeBuilder({ page: panel }).withTags(TAGS).analyze()
  expect(r.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([])
})

test('bàn phím: chuyển tab bằng mũi tên, Esc đóng editor và trả focus', async ({ panel, api }) => {
  await api.send('POST', '/notes', { content: 'abc', title: 'Mẫu' })
  await panel.reload()
  await panel.getByRole('tab', { name: 'Thư viện' }).focus()
  await panel.keyboard.press('ArrowRight')
  // tab "Tìm kiếm" ẩn mặc định (đã gộp vào thanh tìm của Thư viện) → tab kế tiếp là "Tìm trong trang"
  await expect(panel.getByRole('tab', { name: 'Tìm trong trang' })).toHaveAttribute('aria-selected', 'true')
  await expect(panel.getByRole('tab', { name: 'Tìm trong trang' })).toBeFocused()
  await panel.keyboard.press('ArrowLeft')
  await panel.locator('.note-list').getByRole('heading', { name: 'Mẫu' }).click()
  const edit = panel.getByRole('button', { name: 'Sửa' })
  await edit.focus()
  await panel.keyboard.press('Enter')
  await expect(panel.getByRole('heading', { name: 'Sửa ghi chú' })).toBeVisible()
  await panel.keyboard.press('Escape')
  await expect(panel.getByRole('button', { name: 'Lưu' })).toHaveCount(0)
  await expect(edit).toBeFocused()
})

test('popup: chưa đăng nhập hiển thị nút đăng nhập, không vi phạm axe', async ({ context, extId }) => {
  const p = await context.newPage()
  await p.goto(`chrome-extension://${extId}/src/ui/popup/index.html`)
  await expect(p.getByRole('button', { name: 'Đăng nhập bằng Google' })).toBeVisible()
  const r = await new AxeBuilder({ page: p }).withTags(TAGS).analyze()
  expect(r.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([])
})
