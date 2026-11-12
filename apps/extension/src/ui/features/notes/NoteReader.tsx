/**
 * Reader ghi chú (W03 — đọc trước, sửa tại chỗ): breadcrumb, nội dung, tóm tắt AI đã lưu,
 * footer thao tác (Sửa / Xoá / Thử lại AI). Editor nhúng thay modal; tóm tắt mới dùng SummaryPanel
 * (preview → xác nhận lưu, xử lý 402/429).
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
  folders,
  onClose,
  onSaved,
  onDelete,
  onGoSettings,
}: {
  note: Note | null
  folders: Folder[]
  onClose: () => void
  onSaved: (n: Note) => void
  onDelete: (n: Note) => void
  onGoSettings: () => void
}) {
  const [editing, setEditing] = useState(false)
  const wasEditing = useRef(false)
  const editBtn = useRef<HTMLButtonElement>(null)
  const toast = useToast()

  // Đổi ghi chú → luôn quay về chế độ đọc.
  useEffect(() => {
    setEditing(false)
    wasEditing.current = false
  }, [note?.id])

  // Đóng editor (kể cả Esc) → trả focus về nút Sửa (thay hành vi trả focus của Modal cũ).
  useEffect(() => {
    if (!editing && wasEditing.current) {
      wasEditing.current = false
      editBtn.current?.focus()
    }
  }, [editing])

  if (!note) {
    return <EmptyState title="Chưa mở ghi chú nào">Chọn một ghi chú trong danh sách để đọc hoặc sửa.</EmptyState>
  }

  const heading = note.title ?? note.domain ?? 'Ghi chú'
  const folderLabel = folders.find((f) => f.id === note.folder_id)?.name

  const openEdit = () => {
    wasEditing.current = true
    setEditing(true)
  }
  const retryAi = () => {
    void rpc('notes/reindex', { id: note.id })
      .then(onSaved)
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
        <NoteEditor note={note} folders={folders} onClose={() => setEditing(false)} onSaved={onSaved} />
      ) : (
        <>
          <div className="reader-scroll">
            <article className="reader-view" aria-label={heading}>
              <div className="note-kicker">
                <StatusBadge status={note.index_status} />
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
                {note.url && (
                  <>
                    <span className="meta-dot" aria-hidden />
                    <a href={note.url} target="_blank" rel="noreferrer noopener">
                      {note.domain ?? 'nguồn'}
                    </a>
                  </>
                )}
              </div>
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
            </article>
          </div>

          <footer className="reader-footer">
            <span className="save-state">
              <Icon name="check" size={13} />
              Đã lưu · {formatDate(note.updated_at)}
            </span>
            <div className="reader-actions">
              {(note.index_status === 'FAILED' || note.index_status === 'SKIPPED') && (
                <Button variant="ghost" size="sm" onClick={retryAi}>
                  Thử lại AI
                </Button>
              )}
              <Button ref={editBtn} variant="ghost" size="sm" onClick={openEdit}>
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
