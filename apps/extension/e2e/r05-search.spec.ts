/**
 * R05 — nghiệm thu tìm kiếm trên extension: bộ câu hỏi mẫu (có dấu / không dấu), lọc thư mục,
 * mở nguồn, không lộ dữ liệu người khác, hết quota.
 * Tab "Tìm kiếm" đã gộp vào thanh tìm của Thư viện: gõ → lọc nhanh, Enter → tìm sâu bằng AI.
 */
import { expect, sql, test } from './fixtures'

const NOTES = [
  { title: 'Phở bò Hà Nội', content: 'Hầm xương bò khoảng 8 tiếng, gia vị quế hồi thảo quả rang thơm.', url: 'https://amthuc.example/pho' },
  { title: 'Kubernetes', content: 'Deployment quản lý ReplicaSet và hỗ trợ rolling update không gián đoạn.' },
  { title: 'Đà Nẵng', content: 'Cầu Rồng phun lửa lúc 21 giờ tối thứ bảy và chủ nhật.' },
]

async function seedAndIndex(api: any) {
  for (const n of NOTES) await api.send('POST', '/notes', n)
  for (const n of NOTES) await api.waitForNote((x: any) => x.title === n.title && x.index_status === 'READY')
}

for (const [q, title] of [
  ['hầm xương bò bao lâu', 'Phở bò Hà Nội'],
  ['ham xuong bo', 'Phở bò Hà Nội'],
  ['rolling update', 'Kubernetes'],
  ['cau rong phun lua may gio', 'Đà Nẵng'],
] as const) {
  test(`câu hỏi "${q}" → top-1 là "${title}"`, async ({ panel, api }) => {
    await seedAndIndex(api)
    const input = panel.getByLabel('Tìm kiếm hoặc lọc ghi chú')
    await input.fill(q)
    await input.press('Enter')
    await expect(panel.locator('ol.list > li').first().getByRole('heading')).toHaveText(`1. ${title}`)
  })
}

test('kết quả có nguồn + "Mở ghi chú" mở đúng ghi chú ngay trong khung đọc', async ({ panel, api }) => {
  await seedAndIndex(api)
  const input = panel.getByLabel('Tìm kiếm hoặc lọc ghi chú')
  await input.fill('phở bò')
  await input.press('Enter')
  const first = panel.locator('ol.list > li').first()
  await expect(first.getByRole('link', { name: /Mở trang nguồn/ })).toHaveAttribute('href', 'https://amthuc.example/pho')
  await first.getByRole('button', { name: 'Mở ghi chú' }).click()
  await expect(panel.locator('.reader-title')).toHaveText('Phở bò Hà Nội')
})

test('lọc thư mục + không thấy dữ liệu của người khác', async ({ panel, api, email }) => {
  await seedAndIndex(api)
  const f = (await api.send('POST', '/folders', { name: 'Trống' })).body
  // viewport mặc định rộng → rail thư mục hiện (ô chọn thư mục chỉ hiện ở panel hẹp)
  await panel.locator('.folder-nav').getByText('Trống').click()
  const input = panel.getByLabel('Tìm kiếm hoặc lọc ghi chú')
  await input.fill('phở bò')
  await input.press('Enter')
  await expect(panel.getByText('Không có kết quả phù hợp')).toBeVisible()
  // user khác có ghi chú "bí mật" trùng từ khoá → không bao giờ xuất hiện
  const other = await fetch(`${process.env.E2E_API_BASE_URL ?? 'http://localhost:8000/api/v1'}/auth/dev-login`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: `other-${email}` }),
  }).then((r) => r.json())
  await fetch(`${process.env.E2E_API_BASE_URL ?? 'http://localhost:8000/api/v1'}/notes`, {
    method: 'POST', headers: { 'content-type': 'application/json', authorization: `Bearer ${other.access_token}` },
    body: JSON.stringify({ content: 'phở bò bí mật của người khác' }),
  })
  await panel.locator('.folder-nav').getByText('Tất cả ghi chú').click()
  await input.press('Enter')
  await expect(panel.locator('ol.list > li').first()).toBeVisible()
  await expect(panel.getByText(/bí mật của người khác/)).toHaveCount(0)
})

test('hết quota → thông báo rõ + nút xem hạn mức chuyển sang Cài đặt', async ({ panel, api }) => {
  const me = await api.get('/me')
  await api.get('/me/quota')
  await sql('UPDATE quota_accounts SET limit_tokens = 0 WHERE user_id = $1', [me.id])
  const input = panel.getByLabel('Tìm kiếm hoặc lọc ghi chú')
  await input.fill('bất kỳ')
  await input.press('Enter')
  await expect(panel.getByText(/hết hạn mức AI/)).toBeVisible()
  await panel.getByRole('button', { name: 'Xem hạn mức' }).click()
  await expect(panel.getByText('Hạn mức AI')).toBeVisible()
  await expect(panel.getByText(/Đã hết hạn mức/)).toBeVisible()
})
