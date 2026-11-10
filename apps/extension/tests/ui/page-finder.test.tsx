// @vitest-environment happy-dom
/**
 * AutoChunk — PageFinderView: quét → chọn nhiều → lưu 1 ghi chú gộp đúng thứ tự trang; badge theo
 * VERIFY_UNAVAILABLE; full_page; các trạng thái lỗi (402/413/422/quyền/mạng) không treo loading.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppError } from '../../src/shared/errors'
import { installChrome } from '../helpers/chrome'

const { chrome } = installChrome()
const rpc = vi.fn()
vi.mock('../../src/shared/messaging/client', () => ({ rpc: (...a: unknown[]) => rpc(...a), onBroadcast: () => () => undefined }))

const { ToastProvider } = await import('../../src/ui/components')
const { PageFinderView, buildNoteParts } = await import('../../src/ui/features/page-finder/PageFinderView')

const FOLDERS = [
  { id: 'inbox', name: 'Inbox', is_default: true, created_at: '', updated_at: '' },
  { id: 'f1', name: 'Pháp luật', is_default: false, created_at: '', updated_at: '' },
]
const item = (id: string, text: string, verified = true, occ = 0) => ({ id, occ, text, score: 0.71, verified })
const run = (over: Record<string, unknown> = {}) => ({
  mode: 'segments', match_ratio: 0.3, warning: null, total_chars: 900, truncated: false, full_text: null,
  tabId: 5, url: 'https://quochoi.vn/nq', title: 'Danh sách nghị quyết',
  items: [item('b02', 'Nghị quyết 12/2023 về đất đai'), item('b05', 'Nghị quyết 14/2023 thu hồi đất')],
  ...over,
})
const note = { id: 'n1', version: 1 }

const view = () =>
  render(
    <ToastProvider>
      <PageFinderView folders={FOLDERS} onGoSettings={() => undefined} />
    </ToastProvider>,
  )
const scan = async (q = 'nghị quyết đất đai') => {
  fireEvent.change(screen.getByLabelText(/Bạn cần tìm gì/), { target: { value: q } })
  fireEvent.click(screen.getByRole('button', { name: 'Quét trang' }))
}

beforeEach(() => {
  rpc.mockReset()
})
afterEach(cleanup)

describe('buildNoteParts', () => {
  it('gộp theo thứ tự bằng dòng trống; vượt giới hạn → nhiều phần theo biên đoạn, không mất chữ', () => {
    expect(buildNoteParts(['a', 'b', 'c'], 100)).toEqual(['a\n\nb\n\nc'])
    const parts = buildNoteParts(['x'.repeat(40), 'y'.repeat(40), 'z'.repeat(40)], 100)
    expect(parts).toEqual(['x'.repeat(40) + '\n\n' + 'y'.repeat(40), 'z'.repeat(40)])
    const huge = buildNoteParts(['w'.repeat(250)], 100)
    expect(huge.map((p) => p.length)).toEqual([100, 100, 50])
  })
})

describe('PageFinderView', () => {
  it('quét → đoạn đã xác nhận được tích sẵn → lưu 1 ghi chú gộp theo thứ tự trang, title = truy vấn', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'pageMatch/run') return run()
      if (type === 'notes/create') return note
      throw new Error(type)
    })
    view()
    await scan()
    await screen.findByText('Nghị quyết 12/2023 về đất đai')
    expect(rpc).toHaveBeenCalledWith('pageMatch/run', { query: 'nghị quyết đất đai' })
    expect(screen.getAllByText('✓ Đã xác nhận')).toHaveLength(2)
    expect((screen.getByLabelText('Chọn đoạn 1') as HTMLInputElement).checked).toBe(true)
    fireEvent.change(screen.getByLabelText('Lưu vào thư mục'), { target: { value: 'f1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Lưu 2 đoạn thành ghi chú' }))
    await screen.findByText('Đã lưu 2 đoạn thành ghi chú')
    expect(rpc).toHaveBeenCalledWith('notes/create', {
      content: 'Nghị quyết 12/2023 về đất đai\n\nNghị quyết 14/2023 thu hồi đất',
      title: 'nghị quyết đất đai',
      url: 'https://quochoi.vn/nq',
      folderId: 'f1',
    })
  })

  it('bỏ chọn một đoạn → chỉ lưu đoạn còn lại; không chọn gì → nút Lưu bị khoá', async () => {
    rpc.mockImplementation(async (type: string) => (type === 'pageMatch/run' ? run() : note))
    view()
    await scan()
    await screen.findByText('Nghị quyết 12/2023 về đất đai')
    fireEvent.click(screen.getByLabelText('Chọn đoạn 1'))
    fireEvent.click(screen.getByRole('button', { name: 'Lưu 1 đoạn thành ghi chú' }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('notes/create', expect.objectContaining({ content: 'Nghị quyết 14/2023 thu hồi đất', folderId: null })))
    fireEvent.click(screen.getByLabelText('Chọn đoạn 2'))
    expect((screen.getByRole('button', { name: 'Lưu 0 đoạn thành ghi chú' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('VERIFY_UNAVAILABLE → banner cảnh báo, badge "theo điểm", không tích sẵn', async () => {
    rpc.mockResolvedValueOnce(run({ warning: 'VERIFY_UNAVAILABLE', items: [item('b02', 'Đoạn A', false)] }))
    view()
    await scan()
    await screen.findByText(/AI chưa thẩm định được/)
    expect(screen.getByText(/Theo điểm tương đồng · 71%/)).toBeTruthy()
    expect((screen.getByLabelText('Chọn đoạn 1') as HTMLInputElement).checked).toBe(false)
  })

  it('không có đoạn nào → trạng thái rỗng rõ ràng', async () => {
    rpc.mockResolvedValueOnce(run({ items: [] }))
    view()
    await scan()
    await screen.findByText('Không tìm thấy đoạn nào đủ tin cậy')
  })

  it('click "Xem trên trang" → highlight đúng tab + text/occ; không tìm thấy → toast', async () => {
    rpc.mockImplementation(async (type: string) => (type === 'pageMatch/run' ? run() : { ok: false, found: 0, total: 1 }))
    view()
    await scan()
    await screen.findByText('Nghị quyết 12/2023 về đất đai')
    fireEvent.click(screen.getAllByRole('button', { name: 'Xem trên trang' })[1]!)
    await screen.findByText(/Không tìm thấy đoạn trên trang/)
    expect(rpc).toHaveBeenCalledWith('pageMatch/highlight', { tabId: 5, items: [{ text: 'Nghị quyết 14/2023 thu hồi đất', occ: 0 }] })
  })

  it('full_page → banner + "Lưu cả trang" (hỏi lại khi nội dung lớn, tách nhiều ghi chú khi vượt 20 000 ký tự)', async () => {
    const full = Array.from({ length: 30 }, (_, i) => `Đoạn ${i} ` + 'đất đai '.repeat(120)).join('\n\n')
    rpc.mockImplementation(async (type: string) => (type === 'pageMatch/run' ? run({ mode: 'full_page', match_ratio: 0.92, full_text: full, total_chars: full.length }) : note))
    view()
    await scan()
    await screen.findByText(/Hầu như cả trang khớp truy vấn \(92% nội dung\)/)
    fireEvent.click(screen.getByRole('button', { name: 'Lưu cả trang' }))
    await screen.findByText(/sẽ được lưu thành 2 ghi chú/)
    expect(screen.getByText(/token hạn mức AI/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }))
    await screen.findByText('Đã lưu cả trang thành 2 ghi chú')
    const calls = rpc.mock.calls.filter((c) => c[0] === 'notes/create')
    expect(calls.map((c) => c[1].title)).toEqual(['nghị quyết đất đai (1/2)', 'nghị quyết đất đai (2/2)'])
    expect(calls.every((c) => c[1].content.length <= 20_000)).toBe(true)
    expect(calls.map((c) => c[1].content).join('\n\n')).toBe(full)
  })

  it('banner full_page KHÔNG hiện ở mode segments', async () => {
    rpc.mockResolvedValueOnce(run())
    view()
    await scan()
    await screen.findByText('Nghị quyết 12/2023 về đất đai')
    expect(screen.queryByRole('button', { name: 'Lưu cả trang' })).toBeNull()
  })

  it.each([
    ['QUOTA_EXCEEDED', 402, /hết hạn mức AI/, 'Xem hạn mức'],
    ['PAGE_TOO_LONG', 413, /Trang quá dài để quét/, null],
    ['PAGE_NO_CONTENT', 422, /Trang không hỗ trợ quét nội dung/, null],
    ['NETWORK_ERROR', 0, /Không kết nối được máy chủ/, 'Thử lại'],
  ])('lỗi %s → thông báo riêng, không treo loading', async (code, status, text, button) => {
    rpc.mockRejectedValueOnce(new AppError(code, code, status))
    view()
    await scan()
    await screen.findByText(text)
    expect(screen.queryByText(/Đang đọc trang/)).toBeNull()
    expect((screen.getByRole('button', { name: 'Quét trang' }) as HTMLButtonElement).disabled).toBe(false)
    if (button) expect(screen.getByRole('button', { name: button })).toBeTruthy()
  })

  it('chưa có quyền đọc trang → "Cho phép đọc trang" xin quyền tuỳ chọn rồi quét lại', async () => {
    const request = vi.fn(async () => true)
    ;(chrome as unknown as { permissions: unknown }).permissions = { request }
    rpc.mockRejectedValueOnce(new AppError('PAGE_ACCESS_DENIED', 'x', 0)).mockResolvedValueOnce(run())
    view()
    await scan()
    fireEvent.click(await screen.findByRole('button', { name: 'Cho phép đọc trang' }))
    await screen.findByText('Nghị quyết 12/2023 về đất đai')
    expect(request).toHaveBeenCalledWith({ origins: ['http://*/*', 'https://*/*'] })
    expect(rpc.mock.calls.filter((c) => c[0] === 'pageMatch/run')).toHaveLength(2)
  })
})
