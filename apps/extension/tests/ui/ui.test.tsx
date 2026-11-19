// @vitest-environment happy-dom
/**
 * A05, C03, R04, A08, SUM-03 — kiểm thử giao diện với RPC giả lập (không cần background/server).
 */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppError } from '../../src/shared/errors'
import { installChrome } from '../helpers/chrome'

installChrome()
const rpc = vi.fn()
vi.mock('../../src/shared/messaging/client', () => ({ rpc: (...a: unknown[]) => rpc(...a), onBroadcast: () => () => undefined }))

const { ConfidenceBadge, ConfirmDialog, ProgressBar, Tabs, ToastProvider } = await import('../../src/ui/components')
const { NoteEditor } = await import('../../src/ui/features/notes/NoteEditor')
const { NotesView } = await import('../../src/ui/features/notes/NotesView')
const { SearchView } = await import('../../src/ui/features/search/SearchView')
const { SettingsView } = await import('../../src/ui/features/account/SettingsView')
const { SelectionSummary } = await import('../../src/ui/features/summary/SelectionSummary')

const folder = (id: string, name: string, is_default = false) => ({ id, name, is_default, created_at: '', updated_at: '' })
const note = (id: string, over: Record<string, unknown> = {}) => ({
  id, folder_id: 'inbox', url: 'https://a.vn/x', domain: 'a.vn', title: `Tiêu đề ${id}`, content: `Nội dung ${id}`,
  summary_text: null, index_status: 'READY' as const, version: 1, created_at: '2026-10-08T00:00:00Z',
  updated_at: '2026-10-08T00:00:00Z', deleted_at: null, ...over,
})
const FOLDERS = [folder('inbox', 'Inbox', true), folder('f1', 'Học')]
const wrap = (ui: React.ReactElement) => render(<ToastProvider>{ui}</ToastProvider>)

beforeEach(() => {
  rpc.mockReset()
})
afterEach(cleanup)

describe('design system (A05)', () => {
  it('Tabs: ←/→/Home/End chuyển tab, chỉ tab đang chọn có tabIndex 0', () => {
    const onChange = vi.fn()
    render(<Tabs items={[{ key: 'a', label: 'A' }, { key: 'b', label: 'B' }, { key: 'c', label: 'C' }]} value="a" onChange={onChange} />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map((t) => t.tabIndex)).toEqual([0, -1, -1])
    fireEvent.keyDown(tabs[0]!, { key: 'ArrowLeft' })
    fireEvent.keyDown(tabs[0]!, { key: 'ArrowRight' })
    fireEvent.keyDown(tabs[0]!, { key: 'End' })
    expect(onChange.mock.calls.map((c) => c[0])).toEqual(['c', 'b', 'c'])
  })

  it('ProgressBar indeterminate: không có aria-valuenow/aria-valuemax, bar dùng tone chỉ định', () => {
    render(<ProgressBar label="Tiến độ quét" value={0} max={1} tone="accent" indeterminate />)
    const bar = screen.getByRole('progressbar', { name: 'Tiến độ quét' })
    expect(bar.getAttribute('aria-valuenow')).toBeNull()
    expect(bar.getAttribute('aria-valuemax')).toBeNull()
    expect(bar.querySelector('.progress-accent')).toBeTruthy()
  })

  it('ConfirmDialog với confirmText: nút xác nhận khoá cho tới khi gõ đúng', () => {
    const onConfirm = vi.fn()
    render(<ConfirmDialog open title="Xoá?" message="m" confirmText="XOÁ" confirmLabel="Xoá vĩnh viễn" onConfirm={onConfirm} onCancel={() => undefined} />)
    const btn = screen.getByRole('button', { name: 'Xoá vĩnh viễn' }) as HTMLButtonElement
    expect(btn.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText(/Gõ “XOÁ”/), { target: { value: 'xoá' } })
    expect(btn.disabled).toBe(false)
    fireEvent.click(btn)
    expect(onConfirm).toHaveBeenCalled()
  })

  it('Modal: Esc đóng, trả focus về nút mở; Tab giữ focus trong hộp thoại', () => {
    const onCancel = vi.fn()
    function Host() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            Mở hộp thoại
          </button>
          <ConfirmDialog
            open={open}
            title="Xác nhận"
            message="m"
            onConfirm={() => undefined}
            onCancel={() => {
              onCancel()
              setOpen(false)
            }}
          />
        </>
      )
    }
    render(<Host />)
    const opener = screen.getByRole('button', { name: 'Mở hộp thoại' })
    opener.focus()
    fireEvent.click(opener)
    const dialog = screen.getByRole('dialog')
    const focusables = dialog.querySelectorAll<HTMLElement>('button:not([disabled]), input, textarea, select, a[href]')
    const first = focusables[0]!
    const last = focusables[focusables.length - 1]!
    last.focus()
    fireEvent.keyDown(dialog, { key: 'Tab' })
    expect(document.activeElement).toBe(first)
    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })

  it('ConfidenceBadge: kẹp 0..1, phân biệt tin cậy/độ tương đồng và fallback', () => {
    const { rerender } = render(<ConfidenceBadge value={1.4} />)
    expect(screen.getByTitle('AI tin cậy đoạn này khớp truy vấn').textContent).toBe('Độ tin cậy 100%')
    rerender(<ConfidenceBadge value={0.58} verified={false} />)
    const fallback = screen.getByTitle('AI chưa thẩm định — theo độ tương đồng cosine')
    expect(fallback.textContent).toBe('Độ tương đồng 58%')
    expect(fallback.className).toContain('is-unverified')
    rerender(<ConfidenceBadge value={-0.2} kind="similarity" />)
    expect(screen.getByTitle('Độ tương đồng ngữ nghĩa (cosine)').textContent).toBe('Độ tương đồng 0%')
  })
})

describe('thư viện (C03)', () => {
  it('sửa ghi chú gặp 409 → "Ghi đè" lấy version mới nhất rồi lưu bản của người dùng', async () => {
    const onSaved = vi.fn()
    rpc.mockImplementation(async (type: string, p: { version?: number }) => {
      if (type === 'notes/update' && p.version === 1) throw new AppError('NOTE_VERSION_CONFLICT', 'conflict', 409)
      if (type === 'notes/get') return note('n1', { version: 3, content: 'bản máy khác' })
      if (type === 'notes/update') return note('n1', { version: 4, content: 'bản của tôi' })
      throw new Error(type)
    })
    wrap(<NoteEditor note={note('n1')} folders={FOLDERS} onClose={() => undefined} onSaved={onSaved} />)
    fireEvent.change(screen.getByLabelText('Nội dung'), { target: { value: 'bản của tôi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }))
    await screen.findByText(/đã được sửa ở nơi khác/)
    fireEvent.click(screen.getByRole('button', { name: /Ghi đè/ }))
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ version: 4 })))
    expect(rpc).toHaveBeenCalledWith('notes/update', expect.objectContaining({ version: 3, content: 'bản của tôi' }))
  })

  it('không cho lưu nội dung rỗng hoặc vượt 20 000 ký tự', () => {
    wrap(<NoteEditor note={note('n1')} folders={FOLDERS} onClose={() => undefined} onSaved={() => undefined} />)
    const save = screen.getByRole('button', { name: 'Lưu' }) as HTMLButtonElement
    fireEvent.change(screen.getByLabelText('Nội dung'), { target: { value: 'a'.repeat(20_001) } })
    expect(save.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Nội dung'), { target: { value: '   ' } })
    expect(save.disabled).toBe(true)
  })

  it('chọn nhiều → xoá hàng loạt sau khi xác nhận; lọc nhanh theo từ khoá', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'folders/list') return FOLDERS
      if (type === 'notes/list') return [note('n1'), note('n2', { content: 'phở bò' }), note('n3')]
      if (type === 'outbox/list') return []
      if (type === 'notes/delete') return { deleted: 2 }
      throw new Error(type)
    })
    wrap(<NotesView onGoSettings={() => undefined} />)
    await screen.findByText('Tiêu đề n1')
    fireEvent.change(screen.getByLabelText('Tìm kiếm hoặc lọc ghi chú'), { target: { value: 'PHỞ' } })
    expect(screen.queryByText('Tiêu đề n1')).toBeNull()
    fireEvent.change(screen.getByLabelText('Tìm kiếm hoặc lọc ghi chú'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Chọn' }))
    fireEvent.click(screen.getByLabelText('Chọn “Tiêu đề n1”'))
    fireEvent.click(screen.getByLabelText('Chọn “Tiêu đề n3”'))
    fireEvent.click(screen.getByRole('button', { name: 'Xoá (2)' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Xoá' }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('notes/delete', { ids: ['n1', 'n3'] }))
    await waitFor(() => expect(screen.queryByText('Tiêu đề n1')).toBeNull())
    expect(screen.getByText('Tiêu đề n2')).toBeTruthy()
  })

  it('nhóm theo nguồn + summary-first: nhóm có aria-expanded, tóm tắt hiện trước nội dung', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'folders/list') return FOLDERS
      if (type === 'notes/list')
        return [
          note('n1', { domain: 'a.vn', summary_text: 'Tóm tắt n1' }),
          note('n2', { domain: 'a.vn', content: 'Nội dung gốc n2' }),
          note('n3', { domain: 'b.vn' }),
          note('n4', { domain: null, url: null, title: 'Không nguồn' }),
        ]
      if (type === 'outbox/list') return []
      throw new Error(type)
    })
    wrap(<NotesView onGoSettings={() => undefined} />)
    const groupA = await screen.findByRole('region', { name: 'Nguồn a.vn' })
    const toggle = screen.getByRole('button', { name: /a\.vn.*2 ghi chú/ })
    expect(toggle.tagName).toBe('BUTTON')
    toggle.focus()
    expect(document.activeElement).toBe(toggle)
    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    expect(groupA.textContent).toContain('Tóm tắt n1')
    expect(groupA.textContent).toContain('Tóm tắt từ ghi chú')
    // "Không rõ nguồn" luôn cuối danh sách nhóm
    const regions = screen.getAllByRole('region', { name: /^Nguồn / })
    expect(regions.at(-1)!.getAttribute('aria-label')).toBe('Nguồn Không rõ nguồn')
    // đóng nhóm → ẩn danh sách note, aria-expanded=false
    fireEvent.click(toggle)
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByRole('heading', { name: 'Tiêu đề n1' })).toBeNull()
  })

  it('bulk move: chỉ chuyển note đã chọn, dialog chọn thư mục đích rồi reload', async () => {
    let list = [note('n1'), note('n2'), note('n3')]
    rpc.mockImplementation(async (type: string, p: { ids?: string[]; folderId?: string | null }) => {
      if (type === 'folders/list') return FOLDERS
      if (type === 'notes/list') return list
      if (type === 'outbox/list') return []
      if (type === 'notes/move') {
        list = list.filter((n) => !p.ids!.includes(n.id))
        return { moved: p.ids!.length, missing: [] }
      }
      throw new Error(type)
    })
    wrap(<NotesView onGoSettings={() => undefined} />)
    await screen.findByText('Tiêu đề n1')
    fireEvent.click(screen.getByRole('button', { name: 'Chọn' }))
    fireEvent.click(screen.getByLabelText('Chọn “Tiêu đề n1”'))
    fireEvent.click(screen.getByLabelText('Chọn “Tiêu đề n3”'))
    fireEvent.click(screen.getByRole('button', { name: 'Chuyển thư mục' }))
    const dlg = await screen.findByRole('dialog')
    expect(dlg.textContent).toContain('Chỉ 2 ghi chú đã chọn')
    fireEvent.change(screen.getByLabelText('Thư mục đích'), { target: { value: 'f1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Chuyển (2)' }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('notes/move', { ids: ['n1', 'n3'], folderId: 'f1' }))
    await waitFor(() => expect(screen.queryByText('Tiêu đề n1')).toBeNull())
    expect(screen.getByText('Tiêu đề n2')).toBeTruthy()
    expect(screen.getByText('Đã chuyển 2 ghi chú')).toBeTruthy()
  })

  it('"Chọn cả nhóm" chọn đúng các note trong nhóm, không tự chuyển', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'folders/list') return FOLDERS
      if (type === 'notes/list') return [note('n1'), note('n2'), note('n3', { domain: 'b.vn' })]
      if (type === 'outbox/list') return []
      throw new Error(type)
    })
    wrap(<NotesView onGoSettings={() => undefined} />)
    await screen.findByText('Tiêu đề n1')
    fireEvent.click(screen.getByRole('button', { name: 'Chọn' }))
    fireEvent.click(within(screen.getByRole('region', { name: 'Nguồn a.vn' })).getByRole('button', { name: 'Chọn cả nhóm' }))
    expect((screen.getByLabelText('Chọn “Tiêu đề n1”') as HTMLInputElement).checked).toBe(true)
    expect((screen.getByLabelText('Chọn “Tiêu đề n2”') as HTMLInputElement).checked).toBe(true)
    expect((screen.getByLabelText('Chọn “Tiêu đề n3”') as HTMLInputElement).checked).toBe(false)
    expect(rpc).not.toHaveBeenCalledWith('notes/move', expect.anything())
  })

  it('hiện ghi chú chưa gửi được (N06) và cho Gửi lại', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'folders/list') return FOLDERS
      if (type === 'notes/list') return []
      if (type === 'outbox/list') return [{ id: 'p1', snippet: 'đoạn chưa gửi', url: null, title: null, folderId: null, createdAt: 1, attempts: 2, lastError: 'NOTE_TOO_LONG', state: 'failed' }]
      if (type === 'outbox/retry') return undefined
      throw new Error(type)
    })
    wrap(<NotesView onGoSettings={() => undefined} />)
    await screen.findByText(/1 ghi chú chưa gửi được/)
    fireEvent.click(screen.getByRole('button', { name: 'Xem' }))
    expect(screen.getByText(/quá dài/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Gửi lại' }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('outbox/retry', { id: 'p1' }))
  })
})

describe('thanh tìm gộp trong Thư viện (R04 + C03)', () => {
  it('gõ → lọc cục bộ; Enter → tìm sâu AI; "Mở ghi chú" mở ngay trong reader', async () => {
    rpc.mockImplementation(async (type: string, p: { id?: string }) => {
      if (type === 'folders/list') return FOLDERS
      if (type === 'notes/list') return [note('n1'), note('n2', { content: 'phở bò' }), note('n3')]
      if (type === 'outbox/list') return []
      if (type === 'search/query')
        return [{ domain: 'pho.vn', label: 'pho.vn', source_rank: 1, note_count: 1, notes: [{ note_id: 'n2', title: 'Tiêu đề n2', url: 'https://pho.vn', summary: null, snippet: 'hầm xương 8 tiếng', score: 0.03, similarity: 0.62 }] }]
      if (type === 'notes/get') return note(p.id!)
      throw new Error(type)
    })
    wrap(<NotesView onGoSettings={() => undefined} />)
    await screen.findByText('Tiêu đề n1')
    expect(screen.getByText(/tìm sâu bằng AI/)).toBeTruthy()
    // gõ → chỉ lọc cục bộ, chưa gọi AI
    fireEvent.change(screen.getByLabelText('Tìm kiếm hoặc lọc ghi chú'), { target: { value: 'PHỞ' } })
    expect(screen.queryByText('Tiêu đề n1')).toBeNull()
    expect(rpc).not.toHaveBeenCalledWith('search/query', expect.anything())
    // Enter → tìm kiếm ngữ nghĩa với thư mục đang chọn + số nguồn đã chọn
    fireEvent.change(screen.getByLabelText('Số nguồn tối đa'), { target: { value: '10' } })
    fireEvent.submit(screen.getByRole('search'))
    await screen.findByText('Tiêu đề n2')
    expect(rpc).toHaveBeenCalledWith('search/query', { query: 'PHỞ', folderId: null, maxSources: 10 })
    expect(screen.getByRole('link', { name: /Mở trang nguồn/ }).getAttribute('href')).toBe('https://pho.vn')
    // mở ngay trong reader, không cần chuyển tab
    fireEvent.click(screen.getByRole('button', { name: 'Mở ghi chú' }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('notes/get', { id: 'n2' }))
    expect(screen.getByText('Nội dung n2')).toBeTruthy()
    // quay về danh sách (vẫn giữ từ khoá lọc; reader vẫn mở ghi chú vừa xem)
    fireEvent.click(screen.getByRole('button', { name: '← Về danh sách' }))
    expect(screen.getByText('Tiêu đề n2', { selector: '.note-item-title' })).toBeTruthy()
    expect(screen.queryByText('Tiêu đề n1')).toBeNull()
  })

  it('đếm ghi chú theo note_count của nguồn (không phải số note đã tải) + "Xem thêm"', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'folders/list') return FOLDERS
      if (type === 'notes/list') return [note('n1')]
      if (type === 'outbox/list') return []
      if (type === 'search/query')
        return [{
          domain: 'pho.vn',
          label: 'pho.vn',
          source_rank: 1,
          note_count: 12, // tổng đạt ngưỡng; API chỉ trả 3 note đầu
          notes: [1, 2, 3].map((i) => ({
            note_id: `n${i}`,
            title: `Phở ${i}`,
            url: 'https://pho.vn',
            summary: null,
            snippet: 'hầm xương 8 tiếng',
            score: 0.03,
            similarity: 0.62,
          })),
        }]
      throw new Error(type)
    })
    wrap(<NotesView onGoSettings={() => undefined} />)
    await screen.findByText('Tiêu đề n1')
    fireEvent.change(screen.getByLabelText('Tìm kiếm hoặc lọc ghi chú'), { target: { value: 'phở' } })
    fireEvent.submit(screen.getByRole('search'))
    // subtitle phải cộng note_count (12), không phải notes.length (3)
    await screen.findByText(/12 ghi chú cho “phở”/)
    expect(screen.getByText(/và 9 ghi chú khác trong nguồn này/)).toBeTruthy()
  })

  it('tìm sâu hết quota → thông báo rõ + đường tới Cài đặt', async () => {
    const goSettings = vi.fn()
    rpc.mockImplementation(async (type: string) => {
      if (type === 'folders/list') return FOLDERS
      if (type === 'notes/list') return [note('n1')]
      if (type === 'outbox/list') return []
      if (type === 'search/query') throw new AppError('QUOTA_EXCEEDED', 'x', 402)
      throw new Error(type)
    })
    wrap(<NotesView onGoSettings={goSettings} />)
    await screen.findByText('Tiêu đề n1')
    fireEvent.change(screen.getByLabelText('Tìm kiếm hoặc lọc ghi chú'), { target: { value: 'x' } })
    fireEvent.submit(screen.getByRole('search'))
    await screen.findByText(/hết hạn mức AI/)
    fireEvent.click(screen.getByRole('button', { name: 'Xem hạn mức' }))
    expect(goSettings).toHaveBeenCalled()
  })
})

describe('tìm kiếm (R04)', () => {
  it('kết quả kèm nguồn, "Mở ghi chú" chuyển sang thư viện', async () => {
    const onOpen = vi.fn()
    rpc.mockImplementation(async (type: string) => {
      if (type === 'folders/list') return FOLDERS
      if (type === 'search/query') return [{ domain: 'pho.vn', label: 'pho.vn', source_rank: 1, note_count: 1, notes: [{ note_id: 'n9', title: 'Phở bò', url: 'https://pho.vn', summary: null, snippet: 'hầm xương 8 tiếng', score: 0.03, similarity: 0.71 }] }]
      throw new Error(type)
    })
    wrap(<SearchView onOpenNote={onOpen} onGoSettings={() => undefined} />)
    fireEvent.change(screen.getByLabelText('Câu hỏi tìm kiếm'), { target: { value: 'ham xuong' } })
    fireEvent.change(screen.getByLabelText('Số nguồn tối đa'), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: 'Tìm' }))
    await screen.findByText('Phở bò')
    const similarity = screen.getByTitle('Độ tương đồng ngữ nghĩa (cosine)')
    expect(similarity.textContent).toBe('Độ tương đồng 71%')
    expect(similarity.className).toContain('confidence-badge')
    expect(screen.getByText(/tối đa 10/)).toBeTruthy()
    expect(rpc).toHaveBeenCalledWith('search/query', { query: 'ham xuong', folderId: null, maxSources: 10 })
    expect(screen.getByRole('link', { name: /Mở trang nguồn/ }).getAttribute('href')).toBe('https://pho.vn')
    fireEvent.click(screen.getByRole('button', { name: 'Mở ghi chú' }))
    expect(onOpen).toHaveBeenCalledWith('n9')
  })

  it('hết quota → thông báo rõ + đường tới Cài đặt', async () => {
    const goSettings = vi.fn()
    rpc.mockImplementation(async (type: string) => {
      if (type === 'folders/list') return FOLDERS
      throw new AppError('QUOTA_EXCEEDED', 'x', 402)
    })
    wrap(<SearchView onOpenNote={() => undefined} onGoSettings={goSettings} />)
    fireEvent.change(screen.getByLabelText('Câu hỏi tìm kiếm'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Tìm' }))
    await screen.findByText(/hết hạn mức AI/)
    fireEvent.click(screen.getByRole('button', { name: 'Xem hạn mức' }))
    expect(goSettings).toHaveBeenCalled()
  })
})

describe('cài đặt (A08)', () => {
  const session = { signedIn: true, user: { id: 'u', email: 'a@gmail.com', display_name: 'A', avatar_url: null, created_at: '2026-10-01T00:00:00Z' }, authMode: 'google' as const }
  beforeEach(() => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'quota/get') return { limit_tokens: 1000, used_tokens: 950, reserved_tokens: 0, remaining_tokens: 50 }
      if (type === 'prefs/get') return { defaultFolderId: null }
      if (type === 'folders/list') return FOLDERS
      if (type === 'account/delete') return { signedIn: false, user: null }
      if (type === 'prefs/set') return { defaultFolderId: 'f1' }
      throw new Error(type)
    })
  })

  it('hiển thị hạn mức còn lại', async () => {
    wrap(<SettingsView session={session} />)
    await screen.findByText(/còn lại/)
    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('950')
    expect(screen.queryByRole('button', { name: 'Tạo lại hạn mức' })).toBeNull()
  })

  it('BYOK hết hạn mức: banner + nút Đặt lại số liệu, không copy "không giới hạn" (D6)', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'quota/get') return { billing_mode: 'byok', limit_tokens: 1000, used_tokens: 1000, reserved_tokens: 0, remaining_tokens: 0 }
      if (type === 'prefs/get') return { defaultFolderId: null }
      if (type === 'folders/list') return FOLDERS
      throw new Error(type)
    })
    wrap(<SettingsView session={session} />)
    expect(await screen.findByText(/Đã hết hạn mức/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Đặt lại số liệu' })).toBeTruthy()
    expect(screen.queryByText(/không giới hạn/)).toBeNull() // copy cũ đã sửa đúng D6
  })

  it('server hết hạn mức: banner như cũ, không có nút reset', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'quota/get') return { billing_mode: 'server', limit_tokens: 1000, used_tokens: 1000, reserved_tokens: 0, remaining_tokens: 0 }
      if (type === 'prefs/get') return { defaultFolderId: null }
      if (type === 'folders/list') return FOLDERS
      throw new Error(type)
    })
    wrap(<SettingsView session={session} />)
    expect(await screen.findByText(/Đã hết hạn mức/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Đặt lại số liệu' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Tạo lại hạn mức' })).toBeNull()
  })

  it('BYOK còn hạn mức: không banner, vẫn có nút Đặt lại số liệu', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'quota/get') return { billing_mode: 'byok', limit_tokens: 1000, used_tokens: 950, reserved_tokens: 0, remaining_tokens: 50 }
      if (type === 'prefs/get') return { defaultFolderId: null }
      if (type === 'folders/list') return FOLDERS
      throw new Error(type)
    })
    wrap(<SettingsView session={session} />)
    await screen.findByText(/còn lại/)
    expect(screen.queryByText(/Đã hết hạn mức/)).toBeNull()
    expect(screen.getByRole('button', { name: 'Đặt lại số liệu' })).toBeTruthy()
  })

  it('bản demo: tạo lại hạn mức về mức mặc định', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'quota/get') return { limit_tokens: 1000, used_tokens: 950, reserved_tokens: 0, remaining_tokens: 50 }
      if (type === 'quota/reset') return { limit_tokens: 1000, used_tokens: 0, reserved_tokens: 0, remaining_tokens: 1000 }
      if (type === 'prefs/get') return { defaultFolderId: null }
      if (type === 'folders/list') return FOLDERS
      throw new Error(type)
    })
    wrap(<SettingsView session={session} demo />)
    fireEvent.click(await screen.findByRole('button', { name: 'Tạo lại hạn mức' }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('quota/reset'))
    await waitFor(() => expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('0'))
    expect(screen.getByText(/còn lại/).textContent).toMatch(/1\.000/)
  })

  it('xoá tài khoản cần 2 bước + gõ XOÁ', async () => {
    wrap(<SettingsView session={session} />)
    fireEvent.click(screen.getByRole('button', { name: 'Xoá tài khoản…' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Tiếp tục' }))
    const final = (await screen.findByRole('button', { name: 'Xoá vĩnh viễn' })) as HTMLButtonElement
    expect(final.disabled).toBe(true)
    expect(rpc).not.toHaveBeenCalledWith('account/delete', undefined)
    fireEvent.change(screen.getByLabelText(/Gõ “XOÁ”/), { target: { value: 'XOÁ' } })
    await act(async () => fireEvent.click(final))
    expect(rpc).toHaveBeenCalledWith('account/delete')
  })

  it('đổi thư mục mặc định khi lưu nhanh (C04)', async () => {
    wrap(<SettingsView session={session} />)
    const sel = await screen.findByLabelText(/Thư mục mặc định/)
    await waitFor(() => expect((sel as HTMLSelectElement).disabled).toBe(false))
    fireEvent.change(sel, { target: { value: 'f1' } })
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('prefs/set', { defaultFolderId: 'f1' }))
  })

  it('bật lại tab Tìm kiếm (đã gộp vào Thư viện) và báo ngay cho App', async () => {
    const onPrefs = vi.fn()
    rpc.mockImplementation(async (type: string, p: Record<string, unknown>) => {
      if (type === 'quota/get') return { limit_tokens: 1000, used_tokens: 950, reserved_tokens: 0, remaining_tokens: 50 }
      if (type === 'prefs/get') return { defaultFolderId: null, showSearchTab: false }
      if (type === 'prefs/set') return { ...p }
      if (type === 'folders/list') return FOLDERS
      throw new Error(type)
    })
    wrap(<SettingsView session={session} onPrefsChanged={onPrefs} />)
    const cb = (await screen.findByRole('checkbox', { name: /Hiện tab “Tìm kiếm”/ })) as HTMLInputElement
    expect(cb.checked).toBe(false)
    fireEvent.click(cb)
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('prefs/set', { showSearchTab: true }))
    expect(onPrefs).toHaveBeenCalledWith(expect.objectContaining({ showSearchTab: true }))
  })
})

describe('tóm tắt vùng chọn (SUM-03)', () => {
  it('tự tạo bản xem trước rồi "Lưu thành ghi chú" vào thư mục đã chọn', async () => {
    const onDone = vi.fn()
    rpc.mockImplementation(async (type: string) => {
      if (type === 'summary/preview') return { summary: '- ý chính', tokens_used: 10, request_id: 'r' }
      if (type === 'summary/saveSelection') return note('n1')
      throw new Error(type)
    })
    const sel = { text: 'Đoạn văn dài', url: 'https://a.vn', title: 'Trang A', truncated: false, at: 1 }
    wrap(<SelectionSummary selection={sel} folders={FOLDERS} onDone={onDone} onGoSettings={() => undefined} />)
    await screen.findByText('- ý chính')
    expect(screen.getByText('Bản xem trước — chưa lưu')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Lưu vào thư mục'), { target: { value: 'f1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Lưu thành ghi chú' }))
    await waitFor(() => expect(onDone).toHaveBeenCalled())
    expect(rpc).toHaveBeenCalledWith('summary/saveSelection', expect.objectContaining({ summary: '- ý chính', folderId: 'f1', text: 'Đoạn văn dài' }))
  })
})
