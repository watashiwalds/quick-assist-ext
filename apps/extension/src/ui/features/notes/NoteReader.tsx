/**
 * Reader ghi chú (W03 — đọc trước, sửa tại chỗ): breadcrumb, nội dung, tóm tắt AI đã lưu,
 * footer thao tác (Sửa / Xoá / Thử lại AI).
 *
 * D2 — tài liệu nhiều part: reader GỘP read-only hiển thị mọi part theo thứ tự kèm trạng thái
 * chỉ mục; mỗi part sửa riêng như ghi chú thường (không sửa toàn văn). Editor nhúng thay modal;
 * tóm tắt mới dùng SummaryPanel (preview → xác nhận lưu, xử lý 402/429).
 */
import { useEffect, useRef, useState } from 'react'
import type { Folder, Note } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Button, EmptyState, Icon, StatusBadge, useToast } from '../../components'
import { toSerialized, userMessage } from '@/shared/errors'
import { formatDate } from '../../lib/hooks'
import { SummaryPanel } from '../summary/SummaryPanel'
import { NoteEditor } from './NoteEditor'

export function NoteReader({
  note,
  parts,
  folders,
  onClose,
  onSaved,
  onDelete,
  onGoSettings,
}: {
  note: Note | null
  /** Toàn bộ part của tài liệu (nếu đã có trong cache) — thiếu sẽ tự tải theo document_id. */
  parts?: Note[]
  folders: Folder[]
  onClose: () => void
  onSaved: (n: Note) => void
  onDelete: (n: Note) => void
  onGoSettings: () => void
}) {
  const [editing, setEditing] = useState<Note | null>(null)
  const [fetched, setFetched] = useState<Note[]>([])
  const [live, setLive] = useState<Note[]>([])
  const wasEditing = useRef(false)
  const editBtn = useRef<HTMLButtonElement>(null)
  const toast = useToast()

  // Đổi ghi chú → luôn quay về chế độ đọc.
  useEffect(() => {
    setEditing(null)
    setLive([])
    wasEditing.current = false
  }, [note?.id])

  // Mở từ tìm kiếm: cache có thể chưa đủ part → tải danh sách theo document_id.
  useEffect(() => {
    if (!note?.document_id || (parts && parts.length >= note.part_count)) {
      setFetched([])
      return
    }
    let cancelled = false
    void rpc('notes/list', { folderId: null })
      .then((list) => {
        if (cancelled) return
        setFetched(
          list
            .filter((n) => n.document_id === note.document_id)
            .sort((a, b) => a.part_index - b.part_index),
        )
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [note?.id, note?.document_id, note?.part_count, parts])

  // Đóng editor (kể cả Esc) → trả focus về nút Sửa (thay hành vi trả focus của Modal cũ).
  useEffect(() => {
    if (!editing && wasEditing.current) {
      wasEditing.current = false
      editBtn.current?.focus()
    }
  }, [editing])

  // Tài liệu đang tạo chỉ mục: đồng bộ định kỳ để cập nhật trạng thái từng part, dừng khi xong.
  const knownParts = live.length > 0 ? live : parts && parts.length >= fetched.length ? parts : fetched
  const anyProcessing = !!note?.document_id && (knownParts.length > 0 ? knownParts : [note]).some((p) => p?.index_status === 'PROCESSING')
  useEffect(() => {
    if (!note?.document_id || !anyProcessing) return
    let cancelled = false
    const tick = async () => {
      try {
        await rpc('notes/sync')
        const list = await rpc('notes/list', { folderId: null })
        if (cancelled) return
        const next = list.filter((n) => n.document_id === note.document_id).sort((a, b) => a.part_index - b.part_index)
        if (next.length > 0) setLive(next)
      } catch {
        // Lỗi mạng: giữ trạng thái hiện tại, lần sau thử lại.
      }
    }
    void tick()
    const timer = setInterval(() => void tick(), 5_000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [note?.id, note?.document_id, anyProcessing])

  if (!note) {
    return <EmptyState title="Chưa mở ghi chú nào">Chọn một ghi chú trong danh sách để đọc hoặc sửa.</EmptyState>
  }

  // Ưu tiên dữ liệu mới nhất: polling → cache từ Thư viện → vừa tải theo document_id.
  const merged = (
    live.length > 0 ? live : parts && parts.length >= fetched.length ? parts : fetched.length > 0 ? fetched : [note]
  )
    .slice()
    .sort((a, b) => a.part_index - b.part_index)
  const isDocument = merged.length > 1
  const heading = note.title ?? note.domain ?? 'Ghi chú'
  const folderLabel = folders.find((f) => f.id === note.folder_id)?.name
  const processing = merged.some((p) => p.index_status === 'PROCESSING')

  const openEdit = (target: Note) => {
    wasEditing.current = true
    setEditing(target)
  }
  const retryAi = (target: Note) => {
    void rpc('notes/reindex', { id: target.id })
      .then((n) => {
        onSaved(n)
        toast('Đang tạo lại chỉ mục cho phần này')
      })
      .catch((e) => toast(userMessage(toSerialized(e)), 'error'))
  }

  return (
    <>
      <div className="reader-toolbar">
        <nav className="breadcrumb" aria-label="Vị trí">
          <button type="button" className="crumb" onClick={onClose}>
            Thư viện
          </button>
          <span className="meta-dot" aria-hidden />
          <span className="crumb-current">{folderLabel ?? 'Thư mục'}</span>
        </nav>
        <Button variant="ghost" size="sm" aria-label="Đóng ghi chú" title="Đóng" onClick={onClose}>
          <Icon name="x" size={15} />
        </Button>
      </div>

      {editing ? (
        <NoteEditor note={editing} folders={folders} onClose={() => setEditing(null)} onSaved={onSaved} />
      ) : (
        <>
          <div className="reader-scroll">
            <article className="reader-view" aria-label={heading}>
              <div className="note-kicker">
                <StatusBadge status={note.index_status} />
                {isDocument && (
                  <span className="folder-pill">
                    <Icon name="layers" size={12} />
                    Tài liệu {merged.length} phần
                  </span>
                )}
                {folderLabel && (
                  <span className="folder-pill">
                    <Icon name="folder" size={12} />
                    {folderLabel}
                  </span>
                )}
              </div>
              <h2 className="reader-title">{heading}</h2>
              <div className="reader-meta">
                <span>{formatDate(note.created_at)}</span>
                {isDocument && note.original_chars != null && (
                  <>
                    <span className="meta-dot" aria-hidden />
                    <span>{note.original_chars.toLocaleString('vi-VN')} ký tự</span>
                  </>
                )}
                {note.url && (
                  <>
                    <span className="meta-dot" aria-hidden />
                    <a href={note.url} target="_blank" rel="noreferrer noopener">
                      {note.domain ?? 'nguồn'}
                    </a>
                  </>
                )}
              </div>

              {isDocument ? (
                <>
                  {processing && (
                    <p className="muted" role="status">
                      Đang tạo chỉ mục tìm kiếm cho một số phần — trạng thái tự cập nhật khi xong.
                    </p>
                  )}
                  <ol className="doc-parts">
                    {merged.map((p) => (
                      <li key={p.id} className="doc-part">
                        <div className="doc-part-head">
                          <strong>
                            Phần {p.part_index + 1}/{p.part_count}
                          </strong>
                          <StatusBadge status={p.index_status} />
                          <span className="doc-part-chars">{p.content.length.toLocaleString('vi-VN')} ký tự</span>
                          {(p.index_status === 'FAILED' || p.index_status === 'SKIPPED') && (
                            <Button variant="ghost" size="sm" onClick={() => retryAi(p)}>
                              Thử lại AI
                            </Button>
                          )}
                          <Button variant="ghost" size="sm" onClick={() => openEdit(p)}>
                            <Icon name="edit" size={14} />
                            Sửa phần
                          </Button>
                        </div>
                        <div className="reader-body prewrap">{p.content}</div>
                      </li>
                    ))}
                  </ol>
                </>
              ) : (
                <>
                  <div className="reader-body prewrap">{note.content}</div>
                  {note.summary_text && (
                    <details className="summary-card" open>
                      <summary>
                        <Icon name="sparkles" size={14} />
                        Tóm tắt AI
                        <span className="summary-badge">Đã lưu</span>
                        <Icon name="chevron-down" size={14} className="summary-chevron" />
                      </summary>
                      <div className="prewrap">{note.summary_text}</div>
                    </details>
                  )}
                  <SummaryPanel note={note} onSaved={onSaved} onGoSettings={onGoSettings} />
                </>
              )}
            </article>
          </div>

          <footer className="reader-footer">
            <span className="save-state">
              <Icon name="check" size={13} />
              Đã lưu · {formatDate(note.updated_at)}
            </span>
            <div className="reader-actions">
              {(note.index_status === 'FAILED' || note.index_status === 'SKIPPED') && (
                <Button variant="ghost" size="sm" onClick={() => retryAi(note)}>
                  Thử lại AI
                </Button>
              )}
              <Button ref={editBtn} variant="ghost" size="sm" onClick={() => openEdit(note)}>
                <Icon name="edit" size={15} />
                Sửa
              </Button>
              <Button variant="danger-ghost" size="sm" onClick={() => onDelete(note)}>
                <Icon name="trash" size={15} />
                Xoá
              </Button>
            </div>
          </footer>
        </>
      )}
    </>
  )
}
