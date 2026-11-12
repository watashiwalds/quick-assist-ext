/**
 * Sửa ghi chú (C03, kịch bản #5) — form nhúng trong reader (W03: thay modal ở layout rộng):
 * tiêu đề, nội dung, thư mục. PATCH kèm version;
 * 409 → cho người dùng chọn "Xem bản mới nhất" (bỏ thay đổi) hoặc "Ghi đè bằng bản của tôi".
 */
import { useEffect, useState } from 'react'
import type { Folder, Note } from '@/shared/api/types'
import { config } from '@/shared/config'
import { rpc } from '@/shared/messaging/client'
import { Banner, Button, ErrorState, Field, Input, Select, TextArea, useToast } from '../../components'
import { useAction } from '../../lib/hooks'

export function NoteEditor({ note, folders, onClose, onSaved }: { note: Note | null; folders: Folder[]; onClose: () => void; onSaved: (n: Note) => void }) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [folderId, setFolderId] = useState('')
  const [base, setBase] = useState<Note | null>(null)
  const [conflict, setConflict] = useState<Note | null>(null)
  const save = useAction()
  const toast = useToast()

  useEffect(() => {
    if (!note) return
    setBase(note)
    setTitle(note.title ?? '')
    setContent(note.content)
    setFolderId(note.folder_id)
    setConflict(null)
    save.clearError()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [note?.id])

  if (!note || !base) return null
  const tooLong = content.length > config.maxNoteChars
  const unchanged = title === (base.title ?? '') && content === base.content && folderId === base.folder_id

  const submit = async (version: number) => {
    const saved = await save.run(() =>
      rpc('notes/update', {
        id: base.id,
        version,
        ...(title !== (base.title ?? '') ? { title } : {}),
        ...(content !== base.content ? { content } : {}),
        ...(folderId !== base.folder_id ? { folderId } : {}),
      }),
    )
    if (saved) {
      toast(saved.content !== base.content ? 'Đã lưu — đang cập nhật chỉ mục tìm kiếm' : 'Đã lưu thay đổi')
      onSaved(saved)
      onClose()
    }
  }

  const onSubmit = async () => {
    await submit(base.version)
  }
  const isConflict = save.error?.code === 'NOTE_VERSION_CONFLICT'

  return (
    <form
      className="reader-editor"
      aria-labelledby="editor-title"
      onSubmit={(e) => {
        e.preventDefault()
        void onSubmit()
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape' && !save.busy) {
          e.stopPropagation()
          onClose()
        }
      }}
    >
      <header className="editor-head">
        <h2 className="editor-title" id="editor-title">
          Sửa ghi chú
        </h2>
        <p className="editor-subtitle">Thay đổi chỉ được lưu khi bạn bấm Lưu.</p>
      </header>

      <div className="editor-body">
        <div className="stack">
          <Field label="Tiêu đề">{(id) => <Input id={id} value={title} maxLength={500} autoFocus onChange={(e) => setTitle(e.target.value)} />}</Field>
          <Field
            label="Nội dung"
            hint={`${content.length.toLocaleString('vi-VN')} / ${config.maxNoteChars.toLocaleString('vi-VN')} ký tự`}
            error={tooLong ? 'Nội dung quá dài' : !content.trim() ? 'Nội dung không được để trống' : undefined}
          >
            {(id) => <TextArea id={id} value={content} rows={8} onChange={(e) => setContent(e.target.value)} />}
          </Field>
          <Field label="Thư mục">
            {(id) => (
              <Select id={id} value={folderId} onChange={(e) => setFolderId(e.target.value)}>
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {isConflict ? (
            <Banner tone="warn">
              <div className="stack">
                <span>Ghi chú đã được sửa ở nơi khác trong lúc bạn chỉnh.</span>
                <div className="row">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      void save.run(async () => {
                        const latest = await rpc('notes/get', { id: base.id })
                        setConflict(latest)
                        setBase(latest)
                        setTitle(latest.title ?? '')
                        setContent(latest.content)
                        setFolderId(latest.folder_id)
                        onSaved(latest)
                      })
                    }
                  >
                    Xem bản mới nhất (bỏ thay đổi của tôi)
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() =>
                      void save.run(async () => {
                        const latest = await rpc('notes/get', { id: base.id })
                        const saved = await rpc('notes/update', {
                          id: base.id,
                          version: latest.version,
                          title,
                          content,
                          folderId: folderId !== latest.folder_id ? folderId : undefined,
                        })
                        toast('Đã ghi đè bằng bản của bạn')
                        onSaved(saved)
                        onClose()
                      })
                    }
                  >
                    Ghi đè bằng bản của tôi
                  </Button>
                </div>
              </div>
            </Banner>
          ) : (
            save.error && <ErrorState error={save.error} />
          )}
          {conflict && !isConflict && <Banner tone="info">Đã tải bản mới nhất (phiên bản {conflict.version}).</Banner>}
        </div>
      </div>

      <footer className="reader-footer">
        <span className="save-state save-state-edit">
          <span className="save-state-dot" aria-hidden />
          Chưa lưu thay đổi
        </span>
        <div className="reader-actions">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={save.busy}>
            Huỷ
          </Button>
          <Button type="submit" size="sm" busy={save.busy} disabled={unchanged || tooLong || !content.trim() || isConflict}>
            Lưu
          </Button>
        </div>
      </footer>
    </form>
  )
}
