// @vitest-environment happy-dom
/**
 * A05, C03, R04, A08, SUM-03 — kiểm thử giao diện với RPC giả lập (không cần background/server).
 */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppError } from '../../src/shared/errors'
import { installChrome } from '../helpers/chrome'

installChrome()
const rpc = vi.fn()
vi.mock('../../src/shared/messaging/client', () => ({ rpc: (...a: unknown[]) => rpc(...a), onBroadcast: () => () => undefined }))

const { ConfirmDialog, Tabs, ToastProvider } = await import('../../src/ui/components')
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
    fireEvent.change(screen.getByLabelText('Lọc ghi chú theo từ khoá'), { target: { value: 'PHỞ' } })
    expect(screen.queryByText('Tiêu đề n1')).toBeNull()
    fireEvent.change(screen.getByLabelText('Lọc ghi chú theo từ khoá'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Chọn' }))
    fireEvent.click(screen.getByLabelText('Chọn “Tiêu đề n1”'))
    fireEvent.click(screen.getByLabelText('Chọn “Tiêu đề n3”'))
    fireEvent.click(screen.getByRole('button', { name: 'Xoá (2)' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Xoá' }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('notes/delete', { ids: ['n1', 'n3'] }))
    await waitFor(() => expect(screen.queryByText('Tiêu đề n1')).toBeNull())
    expect(screen.getByText('Tiêu đề n2')).toBeTruthy()
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

describe('tìm kiếm (R04)', () => {
  it('kết quả kèm nguồn, "Mở ghi chú" chuyển sang thư viện', async () => {
    const onOpen = vi.fn()
    rpc.mockImplementation(async (type: string) => {
      if (type === 'folders/list') return FOLDERS
      if (type === 'search/query') return [{ chunk_id: 'c1', note_id: 'n9', text: 'hầm xương 8 tiếng', score: 0.03, note_title: 'Phở bò', note_url: 'https://pho.vn', folder_id: 'inbox' }]
      throw new Error(type)
    })
    wrap(<SearchView onOpenNote={onOpen} onGoSettings={() => undefined} />)
    fireEvent.change(screen.getByLabelText('Câu hỏi tìm kiếm'), { target: { value: 'ham xuong' } })
    fireEvent.change(screen.getByLabelText('Số kết quả tối đa'), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: 'Tìm' }))
    await screen.findByText('1. Phở bò')
    expect(screen.getByText(/tối đa 10/)).toBeTruthy()
    expect(rpc).toHaveBeenCalledWith('search/query', { query: 'ham xuong', folderId: null, topK: 10 })
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
  const session = { signedIn: true, user: { id: 'u', email: 'a@gmail.com', display_name: 'A', avatar_url: null, created_at: '2026-10-01T00:00:00Z' } }
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
