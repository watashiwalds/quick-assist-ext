/**
 * Tóm tắt (SDS §5.1.4): tạo PREVIEW → người dùng xác nhận mới lưu vào note.
 * Owner UI: task SUM-02. Gắn component này vào thẻ note trong NotesView.
 */
import { useState } from 'react'
import type { Note } from '@/shared/api/types'
import { AppError, type SerializedError } from '@/shared/errors'
import { rpc } from '@/shared/messaging/client'
import { Button, ErrorState, Spinner } from '../../components'

export function SummaryPanel({ note, onSaved }: { note: Note; onSaved: (n: Note) => void }) {
  const [preview, setPreview] = useState<string>()
  const [error, setError] = useState<SerializedError>()
  const [busy, setBusy] = useState(false)

  const run = async (fn: () => Promise<void>) => {
    setBusy(true)
    setError(undefined)
    try {
      await fn()
    } catch (e) {
      setError(e instanceof AppError ? e.toJSON() : { code: 'UNKNOWN', message: String(e), status: 0 })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      {!preview && (
        <Button variant="ghost" disabled={busy}
          onClick={() => run(async () => setPreview((await rpc('summary/preview', { noteId: note.id })).summary))}>
          Tóm tắt bằng AI
        </Button>
      )}
      {busy && <Spinner label="Đang tóm tắt…" />}
      {error && <ErrorState error={error} />}
      {preview && (
        <div className="card">
          <div style={{ whiteSpace: 'pre-wrap' }}>{preview}</div>
          <div className="row" style={{ marginTop: 6 }}>
            <Button disabled={busy}
              onClick={() => run(async () =>
                onSaved(await rpc('summary/save', { noteId: note.id, version: note.version, summary: preview })))}>
              Lưu tóm tắt
            </Button>
            <Button variant="ghost" onClick={() => setPreview(undefined)}>
              Huỷ
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
