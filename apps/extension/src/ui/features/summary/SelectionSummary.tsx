/**
 * Tóm tắt vùng chọn (SUM-03): menu chuột phải "Tóm tắt đoạn văn bản này" → side panel mở tab
 * này → xem trước → "Lưu thành ghi chú" (nội dung + tóm tắt) hoặc Huỷ.
 */
import { useEffect, useState } from 'react'
import type { Folder } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import type { PendingSelection } from '@/shared/messaging/protocol'
import { Banner, Button, EmptyState, ErrorState, Field, Select, Spinner, useToast } from '../../components'
import { useAction } from '../../lib/hooks'

export function SelectionSummary({ selection, folders, onDone, onGoSettings }: { selection: PendingSelection | null; folders: Folder[]; onDone: () => void; onGoSettings: () => void }) {
  const [preview, setPreview] = useState<string>()
  const [folderId, setFolderId] = useState('')
  const act = useAction()
  const toast = useToast()

  const summarize = () => {
    if (!selection) return
    void act.run(async () => setPreview((await rpc('summary/preview', { text: selection.text })).summary))
  }
  useEffect(() => {
    setPreview(undefined)
    summarize()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection?.at])

  if (!selection) {
    return (
      <EmptyState title="Chưa có đoạn văn bản nào">Bôi đen văn bản trên trang → chuột phải → “Tóm tắt đoạn văn bản này”.</EmptyState>
    )
  }
  return (
    <section className="stack" aria-label="Tóm tắt đoạn văn bản">
      <div className="card">
        <small className="muted">{selection.title ?? selection.url ?? 'Đoạn văn bản đã chọn'}</small>
        <div className="clamp">{selection.text}</div>
      </div>
      {selection.truncated && <Banner tone="warn">Đoạn chọn quá dài, chỉ tóm tắt 30 000 ký tự đầu.</Banner>}
      {act.busy && !preview && <Spinner label="Đang tóm tắt…" />}
      {act.error && (
        <ErrorState
          error={act.error}
          onRetry={act.error.code !== 'QUOTA_EXCEEDED' ? summarize : undefined}
          action={
            act.error.code === 'QUOTA_EXCEEDED' ? (
              <Button variant="link" size="sm" onClick={onGoSettings}>
                Xem hạn mức
              </Button>
            ) : undefined
          }
        />
      )}
      {preview && (
        <div className="card card-preview" aria-label="Bản tóm tắt xem trước">
          <small className="muted">Bản xem trước — chưa lưu</small>
          <div className="prewrap">{preview}</div>
          <Field label="Lưu vào thư mục">
            {(id) => (
              <Select id={id} value={folderId} onChange={(e) => setFolderId(e.target.value)}>
                <option value="">Inbox</option>
                {folders.filter((f) => !f.is_default).map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <div className="row">
            <Button
              busy={act.busy}
              onClick={() =>
                void act
                  .run(() =>
                    rpc('summary/saveSelection', {
                      text: selection.text,
                      url: selection.url,
                      title: selection.title,
                      summary: preview,
                      folderId: folderId || null,
                    }),
                  )
                  .then((n) => {
                    if (!n) return
                    toast('Đã lưu đoạn văn bản kèm bản tóm tắt')
                    onDone()
                  })
              }
            >
              Lưu thành ghi chú
            </Button>
            <Button variant="ghost" onClick={() => void navigator.clipboard?.writeText(preview).then(() => toast('Đã sao chép'))}>
              Sao chép
            </Button>
            <Button variant="ghost" onClick={onDone}>
              Huỷ
            </Button>
          </div>
        </div>
      )}
    </section>
  )
}
