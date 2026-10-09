/**
 * Thư viện ghi chú (C03 — kịch bản #3 + #5): cache-first, lọc theo thư mục + từ khoá, sửa (409),
 * xoá một/nhiều (xác nhận), quản lý thư mục, thử lại AI, tóm tắt, ghi chú chưa gửi (N06).
 */
import { useEffect, useMemo, useState } from 'react'
import type { Note } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Button, ConfirmDialog, EmptyState, ErrorState, Input, Select, Spinner, useToast } from '../../components'
import { useAction, useAsync, useBroadcast } from '../../lib/hooks'
import { FolderManager } from './FolderManager'
import { NoteCard } from './NoteCard'
import { NoteEditor } from './NoteEditor'
import { PendingNotes } from './PendingNotes'

export function NotesView({ openNoteId, onOpened, onGoSettings }: { openNoteId?: string | null; onOpened?: () => void; onGoSettings: () => void }) {
  const [folderId, setFolderId] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [selectMode, setSelectMode] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [editing, setEditing] = useState<Note | null>(null)
  const [confirmIds, setConfirmIds] = useState<string[] | null>(null)
  const [managing, setManaging] = useState(false)
  const [highlight, setHighlight] = useState<string | null>(null)
  const folders = useAsync(() => rpc('folders/list'), [])
  const notes = useAsync(() => rpc('notes/list', { folderId }), [folderId])
  const del = useAction()
  const toast = useToast()
  useBroadcast((e) => {
    if (e.type === 'notes/changed') void notes.reload()
    if (e.type === 'folders/changed') void folders.reload()
  })

  // Mở ghi chú được chọn từ màn Tìm kiếm.
  useEffect(() => {
    if (!openNoteId) return
    void rpc('notes/get', { id: openNoteId })
      .then((n) => {
        setFolderId(null)
        setHighlight(n.id)
        setEditing(n)
      })
      .catch(() => toast('Ghi chú không còn tồn tại', 'error'))
      .finally(() => onOpened?.())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openNoteId])

  const folderName = useMemo(() => new Map((folders.data ?? []).map((f) => [f.id, f.name])), [folders.data])
  const visible = useMemo(() => {
    const q = filter.trim().toLocaleLowerCase('vi')
    const list = notes.data ?? []
    if (!q) return list
    return list.filter((n) => `${n.title ?? ''} ${n.content} ${n.domain ?? ''}`.toLocaleLowerCase('vi').includes(q))
  }, [notes.data, filter])

  const replace = (n: Note) => notes.setData((notes.data ?? []).map((x) => (x.id === n.id ? n : x)).filter((x) => !folderId || x.folder_id === folderId))
  const toggle = (id: string) => setSelected((s) => (s.has(id) ? (s.delete(id), new Set(s)) : new Set(s.add(id))))

  const doDelete = async (ids: string[]) => {
    const r = await del.run(() => rpc('notes/delete', { ids }))
    setConfirmIds(null)
    if (!r) return
    toast(`Đã xoá ${r.deleted} ghi chú`)
    setSelected(new Set())
    setSelectMode(false)
    notes.setData((notes.data ?? []).filter((n) => !ids.includes(n.id)))
  }

  return (
    <section className="stack" aria-label="Thư viện ghi chú">
      <PendingNotes />
      <div className="toolbar">
        <Select aria-label="Lọc theo thư mục" value={folderId ?? ''} onChange={(e) => setFolderId(e.target.value || null)}>
          <option value="">Tất cả thư mục</option>
          {folders.data?.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </Select>
        <Button variant="ghost" size="sm" onClick={() => setManaging(true)} title="Tạo, đổi tên, xoá thư mục">
          Thư mục
        </Button>
      </div>
      <div className="toolbar">
        <Input type="search" aria-label="Lọc ghi chú theo từ khoá" placeholder="Lọc nhanh trong thư viện…" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <Button variant="ghost" size="sm" aria-pressed={selectMode} onClick={() => (setSelectMode(!selectMode), setSelected(new Set()))}>
          {selectMode ? 'Xong' : 'Chọn'}
        </Button>
        <Button variant="ghost" size="sm" title="Đồng bộ với máy chủ" aria-label="Đồng bộ" onClick={() => void rpc('notes/sync').then(notes.reload)}>
          ⟳
        </Button>
      </div>
      {selectMode && (
        <div className="row spread selection-bar">
          <span>Đã chọn {selected.size}</span>
          <div className="row">
            <Button size="sm" variant="ghost" onClick={() => setSelected(new Set(visible.map((n) => n.id)))}>
              Chọn tất cả
            </Button>
            <Button size="sm" variant="danger" disabled={selected.size === 0} onClick={() => setConfirmIds([...selected])}>
              Xoá ({selected.size})
            </Button>
          </div>
        </div>
      )}
      {del.error && <ErrorState error={del.error} />}
      {notes.loading && !notes.data && <Spinner />}
      {notes.error && <ErrorState error={notes.error} onRetry={notes.reload} />}
      {notes.data?.length === 0 && (
        <EmptyState title="Chưa có ghi chú">Bôi đen văn bản trên trang → chuột phải → “Ghi chú văn bản này” (hoặc Alt+Shift+N).</EmptyState>
      )}
      {!!notes.data?.length && visible.length === 0 && <EmptyState title="Không có ghi chú khớp bộ lọc" />}
      <ul className="list" aria-live="polite">
        {visible.map((n) => (
          <NoteCard
            key={n.id}
            note={n}
            folderName={folderId ? undefined : folderName.get(n.folder_id)}
            selectMode={selectMode}
            selected={selected.has(n.id)}
            highlight={highlight === n.id}
            onToggle={() => toggle(n.id)}
            onEdit={() => setEditing(n)}
            onDelete={() => setConfirmIds([n.id])}
            onChanged={replace}
            onGoSettings={onGoSettings}
          />
        ))}
      </ul>
      <NoteEditor note={editing} folders={folders.data ?? []} onClose={() => setEditing(null)} onSaved={replace} />
      <FolderManager open={managing} folders={folders.data ?? []} onClose={() => setManaging(false)} onChanged={() => void folders.reload().then(notes.reload)} />
      <ConfirmDialog
        open={!!confirmIds}
        title={confirmIds && confirmIds.length > 1 ? `Xoá ${confirmIds.length} ghi chú?` : 'Xoá ghi chú?'}
        message="Ghi chú sẽ bị xoá khỏi thư viện và kết quả tìm kiếm trên mọi thiết bị."
        confirmLabel="Xoá"
        danger
        busy={del.busy}
        onCancel={() => setConfirmIds(null)}
        onConfirm={() => void doDelete(confirmIds ?? [])}
      />
    </section>
  )
}
