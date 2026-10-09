/** Tìm kiếm ngữ nghĩa (R04 — kịch bản #4, SDS §5.1.3): câu hỏi + lọc thư mục → đoạn liên quan kèm nguồn. */
import { type FormEvent, useState } from 'react'
import type { SearchHit } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Button, EmptyState, ErrorState, Input, Select, Spinner } from '../../components'
import { useAction, useAsync } from '../../lib/hooks'

export function SearchView({ onOpenNote, onGoSettings }: { onOpenNote: (noteId: string) => void; onGoSettings: () => void }) {
  const [query, setQuery] = useState('')
  const [folderId, setFolderId] = useState<string | null>(null)
  const [hits, setHits] = useState<SearchHit[]>()
  const [asked, setAsked] = useState('')
  const folders = useAsync(() => rpc('folders/list'), [])
  const act = useAction()

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q || act.busy) return
    const r = await act.run(() => rpc('search/query', { query: q, folderId }))
    if (r) {
      setHits(r)
      setAsked(q)
    }
  }

  return (
    <section className="stack" aria-label="Tìm kiếm ghi chú">
      <form className="stack" onSubmit={(e) => void onSubmit(e)} role="search">
        <div className="row">
          <Input
            type="search"
            aria-label="Câu hỏi tìm kiếm"
            placeholder="Bạn đang tìm điều gì? (có thể gõ không dấu)"
            value={query}
            maxLength={1000}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button type="submit" busy={act.busy} disabled={!query.trim()}>
            Tìm
          </Button>
        </div>
        <Select aria-label="Tìm trong thư mục" value={folderId ?? ''} onChange={(e) => setFolderId(e.target.value || null)}>
          <option value="">Trong mọi thư mục</option>
          {folders.data?.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </Select>
      </form>
      {act.busy && <Spinner label="Đang tìm nội dung tương đồng cho bạn…" />}
      {act.error && (
        <ErrorState
          error={act.error}
          action={
            act.error.code === 'QUOTA_EXCEEDED' ? (
              <Button variant="link" size="sm" onClick={onGoSettings}>
                Xem hạn mức
              </Button>
            ) : undefined
          }
        />
      )}
      {!act.busy && hits?.length === 0 && (
        <EmptyState title="Không có kết quả phù hợp">Thử diễn đạt khác, bỏ lọc thư mục, hoặc đợi ghi chú mới chuyển “Sẵn sàng tìm kiếm”.</EmptyState>
      )}
      {!!hits?.length && (
        <p className="muted" aria-live="polite">
          {hits.length} đoạn liên quan nhất tới “{asked}”
        </p>
      )}
      <ol className="list">
        {hits?.map((h, i) => (
          <li key={h.chunk_id} className="card">
            <div className="row spread">
              <h3 className="grow">
                {i + 1}. {h.note_title ?? 'Ghi chú'}
              </h3>
              <small className="muted" title="Điểm liên quan (RRF)">
                {h.score.toFixed(3)}
              </small>
            </div>
            <div className="clamp">{h.text}</div>
            <div className="row actions">
              <Button variant="ghost" size="sm" onClick={() => onOpenNote(h.note_id)}>
                Mở ghi chú
              </Button>
              {h.note_url && (
                <a className="btn btn-ghost btn-sm" href={h.note_url} target="_blank" rel="noreferrer noopener">
                  Mở trang nguồn ↗
                </a>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
