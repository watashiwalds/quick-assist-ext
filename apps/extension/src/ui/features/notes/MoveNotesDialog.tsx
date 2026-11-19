/**
 * Chuyển các ghi chú ĐÃ CHỌN sang thư mục khác (Phase 2 — UX plan §5.2).
 * Không tự động chuyển note chưa chọn; `null` = Inbox (thư mục mặc định của server).
 */
import { useEffect, useState } from 'react'
import type { Folder } from '@/shared/api/types'
import { Button, Field, Modal, Select } from '../../components'

export function MoveNotesDialog({
  open,
  count,
  folders,
  busy,
  onCancel,
  onConfirm,
}: {
  open: boolean
  count: number
  folders: Folder[]
  busy: boolean
  onCancel: () => void
  onConfirm: (folderId: string | null) => void
}) {
  const [folderId, setFolderId] = useState('')
  useEffect(() => {
    if (open) setFolderId('')
  }, [open])

  return (
    <Modal
      open={open}
      title={`Chuyển ${count} ghi chú`}
      onClose={onCancel}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel} disabled={busy}>
            Huỷ
          </Button>
          <Button onClick={() => onConfirm(folderId || null)} busy={busy}>
            Chuyển ({count})
          </Button>
        </>
      }
    >
      <div className="stack">
        <p className="muted">Chỉ {count} ghi chú đã chọn được chuyển; các ghi chú khác giữ nguyên thư mục.</p>
        <Field label="Thư mục đích">
          {(id) => (
            <Select id={id} value={folderId} onChange={(e) => setFolderId(e.target.value)}>
              <option value="">Inbox</option>
              {folders
                .filter((f) => !f.is_default)
                .map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
            </Select>
          )}
        </Field>
      </div>
    </Modal>
  )
}
