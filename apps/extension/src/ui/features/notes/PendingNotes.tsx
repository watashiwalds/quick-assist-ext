/** Ghi chú chưa lên server (N06): đang chờ gửi (mất mạng) và gửi lỗi — Gửi lại / Bỏ. */
import { useState } from 'react'
import { userMessage } from '@/shared/errors'
import { rpc } from '@/shared/messaging/client'
import type { PendingNote } from '@/shared/messaging/protocol'
import { Banner, Button, ConfirmDialog } from '../../components'
import { useAsync, useBroadcast } from '../../lib/hooks'

export function PendingNotes() {
  const pending = useAsync(() => rpc('outbox/list'), [])
  useBroadcast((e) => (e.type === 'outbox/changed' || e.type === 'notes/changed') && void pending.reload())
  const [discard, setDiscard] = useState<PendingNote>()
  const [open, setOpen] = useState(false)

  const items = pending.data ?? []
  const failed = items.filter((i) => i.state === 'failed')
  const queued = items.filter((i) => i.state === 'queued' && i.attempts > 0)
  if (failed.length === 0 && queued.length === 0) return null

  return (
    <section aria-label="Ghi chú chưa gửi" className="pending">
      <Banner tone={failed.length ? 'error' : 'warn'}>
        <div className="row spread">
          <span>
            {failed.length > 0 && <strong>{failed.length} ghi chú chưa gửi được. </strong>}
            {queued.length > 0 && <span>{queued.length} ghi chú đang chờ mạng để gửi lại.</span>}
          </span>
          <Button variant="link" size="sm" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? 'Ẩn' : 'Xem'}
          </Button>
        </div>
      </Banner>
      {open && (
        <ul className="list">
          {[...failed, ...queued].map((p) => (
            <li key={p.id} className="card card-pending">
              <div className="clamp">{p.snippet}</div>
              <small className="muted">
                {p.state === 'failed'
                  ? `Lỗi: ${userMessage({ code: p.lastError ?? 'UNKNOWN', message: p.lastError ?? '', status: 0 })}`
                  : `Đã thử ${p.attempts} lần — tự gửi lại khi có mạng`}
              </small>
              <div className="row">
                <Button size="sm" onClick={() => void rpc('outbox/retry', { id: p.id }).then(pending.reload)}>
                  Gửi lại
                </Button>
                {p.state === 'failed' && (
                  <Button size="sm" variant="ghost" onClick={() => setDiscard(p)}>
                    Bỏ ghi chú này
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={!!discard}
        title="Bỏ ghi chú chưa gửi?"
        message="Ghi chú này chưa được lưu lên máy chủ. Bỏ đi sẽ mất vĩnh viễn."
        confirmLabel="Bỏ ghi chú"
        danger
        onCancel={() => setDiscard(undefined)}
        onConfirm={() => {
          const id = discard!.id
          setDiscard(undefined)
          void rpc('outbox/discard', { id }).then(pending.reload)
        }}
      />
    </section>
  )
}
