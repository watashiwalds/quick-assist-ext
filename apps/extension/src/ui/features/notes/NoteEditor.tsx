/**
 * Sửa ghi chú (C03, kịch bản #5) — form nhúng trong reader (W03: thay modal ở layout rộng):
 * tiêu đề, nội dung, thư mục. PATCH kèm version;
 * 409 → cho người dùng chọn "Xem bản mới nhất" (bỏ thay đổi) hoặc "Ghi đè bằng bản của tôi".
 */
import { useEffect, useState } from 'react'
import type { Folder, Note } from '@/shared/api/types'
import { config } from '@/shared/config'
import { rpc } from '@/shared/messaging/client'
import { estimateChunks, resolveSplitChars, splitText } from '@/shared/notes/split'
import { Banner, Button, ConfirmDialog, ErrorState, Field, Input, Select, TextArea, useToast } from '../../components'
import { useAction, useAsync } from '../../lib/hooks'

/** Ước lượng token hạn mức AI để tạo chỉ mục (≈ 2 ký tự/token như backend). */
const estimateTokens = (chars: number) => Math.ceil(chars / 2)

export function NoteEditor({ note, folders, onClose, onSaved }: { note: Note | null; folders: Folder[]; onClose: () => void; onSaved: (n: Note) => void }) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [folderId, setFolderId] = useState('')
  const [base, setBase] = useState<Note | null>(null)
  const [conflict, setConflict] = useState<Note | null>(null)
  const [splitParts, setSplitParts] = useState<string[] | null>(null)
  const save = useAction()
  const toast = useToast()
  const prefs = useAsync(() => rpc('prefs/get'), [])
  const maxChars = resolveSplitChars(prefs.data?.splitChars)

  useEffect(() => {
    if (!note) return
    setBase(note)
    setTitle(note.title ?? '')
    setContent(note.content)
    setFolderId(note.folder_id)
    setConflict(null)
    setSplitParts(null)
    save.clearError()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [note?.id])

  if (!note || !base) return null
  const changed = content !== base.content
  /** Vượt ngưỡng chia đã chọn → tài liệu mới được chia phần (chỉ với ghi chú thường). */
  const overPreset = changed && content.length > maxChars
  /** Part của tài liệu không được vượt trần cứng của server (không chia lại part — ngoài MVP). */
  const overServer = changed && content.length > config.maxNoteChars
  const canSplit = overPreset && !base.document_id
  const blocked = !!base.document_id && overServer
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
    if (canSplit) {
      setSplitParts(splitText(content, maxChars))
      return
    }
    if (blocked) return
    await submit(base.version)
  }

  /** Chuyển note thường thành tài liệu nhiều part: tạo document rồi xoá note cũ. */
  const convertToDocument = async () => {
    const parts = splitParts
    if (!parts) return
    setSplitParts(null)
    const created = await save.run(async () => {
      const first = await rpc('notes/create', {
        parts,
        documentId: crypto.randomUUID(),
        title: title.trim() || null,
        url: base.url,
        folderId: folderId || null,
      })
      try {
        await rpc('notes/delete', { ids: [base.id] })
      } catch {
        toast('Đã lưu tài liệu mới nhưng chưa xoá được ghi chú cũ', 'error')
        return first
      }
      toast(`Đã lưu thành tài liệu ${parts.length} phần — đang cập nhật chỉ mục tìm kiếm`)
      return first
    })
    if (created) {
      onSaved(created)
      onClose()
    }
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
            hint={
              canSplit
                ? `${content.length.toLocaleString('vi-VN')} ký tự — sẽ chia thành ${splitText(content, maxChars).length} phần khi lưu`
                : `${content.length.toLocaleString('vi-VN')} / ${maxChars.toLocaleString('vi-VN')} ký tự`
            }
            error={
              blocked
                ? `Mỗi phần tối đa ${config.maxNoteChars.toLocaleString('vi-VN')} ký tự — không thể chia lại một phần của tài liệu`
                : !content.trim()
                  ? 'Nội dung không được để trống'
                  : undefined
            }
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
          <Button type="submit" size="sm" busy={save.busy} disabled={!content.trim() || isConflict || (unchanged && !canSplit) || blocked}>
            Lưu
          </Button>
        </div>
      </footer>

      <ConfirmDialog
        open={!!splitParts}
        title="Lưu thành tài liệu dài?"
        message={
          splitParts
            ? `Nội dung dài ${splitParts.reduce((n, p) => n + p.length, 0).toLocaleString('vi-VN')} ký tự, sẽ được lưu thành MỘT tài liệu gồm ${splitParts.length} phần và thay thế ghi chú hiện tại. Tạo chỉ mục tìm kiếm sẽ dùng khoảng ${estimateTokens(splitParts.reduce((n, p) => n + p.length, 0)).toLocaleString('vi-VN')} token hạn mức AI (≈ ${estimateChunks(splitParts.reduce((n, p) => n + p.length, 0))} chunk).`
            : ''
        }
        confirmLabel="Lưu tài liệu"
        busy={save.busy}
        onCancel={() => setSplitParts(null)}
        onConfirm={() => void convertToDocument()}
      />
    </form>
  )
}
