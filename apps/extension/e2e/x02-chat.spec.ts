/**
 * X01 + X02 — nghiệm thu Hỏi AI trên extension thật: câu trả lời stream về side panel, có danh sách nguồn
 * từ đúng ghi chú của người dùng, mở được ghi chú nguồn, không có ghi chú liên quan thì không gọi LLM,
 * hội thoại giữ khi chuyển tab, "Cuộc trò chuyện mới" xoá hội thoại.
 */
import { expect, test } from './fixtures'

const NOTES = [
  { title: 'Phở bò Hà Nội', content: 'Hầm xương bò khoảng 8 tiếng, gia vị quế hồi thảo quả rang thơm.', url: 'https://amthuc.example/pho' },
  { title: 'Kubernetes', content: 'Deployment quản lý ReplicaSet và hỗ trợ rolling update không gián đoạn.' },
]

async function seedAndIndex(api: any) {
  for (const n of NOTES) await api.send('POST', '/notes', n)
  for (const n of NOTES) await api.waitForNote((x: any) => x.title === n.title && x.index_status === 'READY')
}

test('hỏi → câu trả lời + nguồn từ ghi chú, mở được ghi chú nguồn', async ({ panel, api }) => {
  await seedAndIndex(api)
  await panel.getByRole('tab', { name: 'Hỏi AI' }).click()
  await panel.getByLabel('Câu hỏi về ghi chú').fill('hầm xương bò bao lâu')
  await panel.getByRole('button', { name: 'Gửi' }).click()
  const answer = panel.locator('.chat-ai').first()
  await expect(answer).toContainText('[mock]') // AI giả lập trong môi trường E2E
  await expect(panel.getByRole('button', { name: 'Gửi' })).toBeVisible() // đã xong, hết nút Dừng
  await expect(answer.getByText(/^Nguồn \(\d\)$/)).toBeVisible()
  await expect(answer.getByRole('button', { name: 'Nguồn 1: Phở bò Hà Nội' })).toBeVisible() // trích dẫn [1] bấm được
  const first = answer.locator('.chat-source').first()
  await expect(first).toContainText('[1] Phở bò Hà Nội')
  await expect(first.getByRole('link', { name: /Trang nguồn/ })).toHaveAttribute('href', 'https://amthuc.example/pho')
  await first.getByRole('button', { name: 'Mở ghi chú' }).click()
  await expect(panel.getByRole('dialog', { name: 'Sửa ghi chú' })).toBeVisible()
  await expect(panel.getByLabel('Tiêu đề')).toHaveValue('Phở bò Hà Nội')
})

test('không có ghi chú liên quan → nói rõ, không bịa', async ({ panel }) => {
  await panel.getByRole('tab', { name: 'Hỏi AI' }).click()
  await panel.getByLabel('Câu hỏi về ghi chú').fill('thời tiết sao hoả hôm nay')
  await panel.getByLabel('Câu hỏi về ghi chú').press('Enter')
  await expect(panel.locator('.chat-ai').first()).toContainText('không tìm thấy ghi chú nào liên quan')
})

test('hội thoại giữ khi chuyển tab; "Cuộc trò chuyện mới" xoá', async ({ panel, api }) => {
  await seedAndIndex(api)
  await panel.getByRole('tab', { name: 'Hỏi AI' }).click()
  await panel.getByLabel('Câu hỏi về ghi chú').fill('rolling update')
  await panel.getByRole('button', { name: 'Gửi' }).click()
  await expect(panel.getByRole('button', { name: 'Gửi' })).toBeVisible()
  await panel.getByRole('tab', { name: 'Thư viện' }).click()
  await panel.getByRole('tab', { name: 'Hỏi AI' }).click()
  await expect(panel.locator('.chat-user')).toHaveText(/rolling update/)
  await panel.getByRole('button', { name: 'Cuộc trò chuyện mới' }).click()
  await expect(panel.locator('.chat-msg')).toHaveCount(0)
})
