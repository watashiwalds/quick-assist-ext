/**
 * Tóm tắt ghi chú (SUM-03, SDS §5.1.4): tạo PREVIEW → người dùng xác nhận mới lưu vào note.
 * Gắn vào thẻ ghi chú trong thư viện.
 */
import { useState } from 'react'
import type { Note } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Button, ErrorState, Spinner, useToast } from '../../components'
import { useAction } from '../../lib/hooks'

export function SummaryPanel({ note, onSaved, onGoSettings }: { note: Note; onSaved: (n: Note) => void; onGoSettings?: () => void }) {
  const [preview, setPreview] = useState<string>()
  const act = useAction()
  const toast = useToast()

  return (
    <div className="summary">
      {!preview && !act.busy && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void act.run(async () => setPreview((await rpc('summary/preview', { noteId: note.id })).summary))}
        >
          {note.summary_text ? 'Tóm tắt lại' : 'Tóm tắt bằng AI'}
        </Button>
      )}
      {act.busy && <Spinner label="Đang tóm tắt…" />}
      {act.error && (
        <ErrorState
          error={act.error}
          onRetry={act.error.code === 'AI_UNAVAILABLE' ? () => void act.run(async () => setPreview((await rpc('summary/preview', { noteId: note.id })).summary)) : undefined}
          action={
            act.error.code === 'QUOTA_EXCEEDED' && onGoSettings ? (
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
          <div className="row">
            <Button
              size="sm"
              busy={act.busy}
              onClick={() =>
                void act
                  .run(() => rpc('summary/save', { noteId: note.id, version: note.version, summary: preview }))
                  .then((n) => {
                    if (!n) return
                    setPreview(undefined)
                    toast('Đã lưu bản tóm tắt')
                    onSaved(n)
                  })
              }
            >
              Lưu tóm tắt
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setPreview(undefined)}>
              Huỷ
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
