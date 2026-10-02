/** Thư viện ghi chú (kịch bản #3 + #5): lọc theo thư mục, xem, xoá, thử lại AI. Owner UI: C03. */
import { useState } from 'react'
import { rpc } from '@/shared/messaging/client'
import { Button, EmptyState, ErrorState, Spinner, StatusBadge } from '../../components'
import { useAsync, useBroadcast } from '../../lib/hooks'

export function NotesView() {
  const [folderId, setFolderId] = useState<string | null>(null)
  const folders = useAsync(() => rpc('folders/list'), [])
  const notes = useAsync(() => rpc('notes/list', { folderId }), [folderId])
  useBroadcast((e) => e.type === 'notes/changed' && void notes.reload())

  return (
    <section>
      <div className="row">
        <select aria-label="Thư mục" value={folderId ?? ''} onChange={(e) => setFolderId(e.target.value || null)}>
          <option value="">Tất cả thư mục</option>
          {folders.data?.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
        <Button variant="ghost" onClick={() => void rpc('notes/sync').then(notes.reload)}>
          Đồng bộ
        </Button>
      </div>

      {notes.loading && !notes.data && <Spinner />}
      {notes.error && <ErrorState error={notes.error} onRetry={notes.reload} />}
      {notes.data?.length === 0 && (
        <EmptyState title="Chưa có ghi chú">Bôi đen văn bản trên trang → chuột phải → “Ghi chú văn bản này”.</EmptyState>
      )}
      <ul className="list">
        {notes.data?.map((n) => (
          <li key={n.id} className="card">
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h3>{n.title ?? n.domain ?? 'Ghi chú'}</h3>
              <StatusBadge status={n.index_status} />
            </div>
            <div className="clamp">{n.content}</div>
            {n.url && (
              <a className="muted" href={n.url} target="_blank" rel="noreferrer noopener">
                {n.domain}
              </a>
            )}
            <div className="row" style={{ marginTop: 6 }}>
              {(n.index_status === 'FAILED' || n.index_status === 'SKIPPED') && (
                <Button variant="ghost" onClick={() => void rpc('notes/reindex', { id: n.id }).then(notes.reload)}>
                  Thử lại AI
                </Button>
              )}
              <Button variant="ghost" onClick={() => void rpc('notes/delete', { ids: [n.id] }).then(notes.reload)}>
                Xoá
              </Button>
              {/* TODO(C03): sửa nội dung (PATCH kèm version, xử lý 409), tóm tắt (SummaryPanel) */}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
