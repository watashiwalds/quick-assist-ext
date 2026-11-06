/** Quản lý thư mục (C03): tạo, đổi tên, xoá (ghi chú chuyển về Inbox). */
import { useState } from 'react'
import type { Folder } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Button, ConfirmDialog, ErrorState, Input, Modal, useToast } from '../../components'
import { useAction } from '../../lib/hooks'

export function FolderManager({ open, folders, onClose, onChanged }: { open: boolean; folders: Folder[]; onClose: () => void; onChanged: () => void }) {
  const [name, setName] = useState('')
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null)
  const [toDelete, setToDelete] = useState<Folder>()
  const act = useAction()
  const toast = useToast()

  const create = async () => {
    if (!name.trim()) return
    if (await act.run(() => rpc('folders/create', { name: name.trim() }))) {
      setName('')
      toast('Đã tạo thư mục')
      onChanged()
    }
  }
  const rename = async () => {
    if (!editing?.name.trim()) return
    if (await act.run(() => rpc('folders/rename', { id: editing.id, name: editing.name.trim() }))) {
      setEditing(null)
      onChanged()
    }
  }

  return (
    <Modal open={open} title="Thư mục" onClose={onClose}>
      <div className="stack">
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault()
            void create()
          }}
        >
          <Input aria-label="Tên thư mục mới" placeholder="Tên thư mục mới" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} />
          <Button type="submit" busy={act.busy} disabled={!name.trim()}>
            Tạo
          </Button>
        </form>
        {act.error && <ErrorState error={act.error} />}
        <ul className="list">
          {folders.map((f) => (
            <li key={f.id} className="row spread folder-row">
              {editing?.id === f.id ? (
                <form
                  className="row grow"
                  onSubmit={(e) => {
                    e.preventDefault()
                    void rename()
                  }}
                >
                  <Input aria-label={`Tên mới cho ${f.name}`} value={editing.name} maxLength={100} autoFocus onChange={(e) => setEditing({ id: f.id, name: e.target.value })} />
                  <Button type="submit" size="sm" busy={act.busy}>
                    Lưu
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                    Huỷ
                  </Button>
                </form>
              ) : (
                <>
                  <span>
                    {f.name} {f.is_default && <small className="muted">(mặc định)</small>}
                  </span>
                  {!f.is_default && (
                    <span className="row">
                      <Button size="sm" variant="ghost" onClick={() => setEditing({ id: f.id, name: f.name })}>
                        Đổi tên
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setToDelete(f)}>
                        Xoá
                      </Button>
                    </span>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      </div>
      <ConfirmDialog
        open={!!toDelete}
        title={`Xoá thư mục “${toDelete?.name ?? ''}”?`}
        message="Các ghi chú trong thư mục sẽ được chuyển về Inbox, không bị xoá."
        confirmLabel="Xoá thư mục"
        danger
        busy={act.busy}
        onCancel={() => setToDelete(undefined)}
        onConfirm={() =>
          void act
            .run(async () => {
              await rpc('folders/delete', { id: toDelete!.id })
              return true
            })
            .then((ok) => {
              setToDelete(undefined)
              if (ok) {
                toast('Đã xoá thư mục, ghi chú đã về Inbox')
                onChanged()
              }
            })
        }
      />
    </Modal>
  )
}
