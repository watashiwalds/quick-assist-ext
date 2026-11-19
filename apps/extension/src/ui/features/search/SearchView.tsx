/** Tìm kiếm ngữ nghĩa (R04 — kịch bản #4, SDS §5.1.3): câu hỏi + lọc thư mục → nguồn/ghi chú
 * liên quan, nhóm theo domain (Phase 2 — dùng chung `SearchResults` với Thư viện). */
import { type FormEvent, useState } from 'react'
import type { SearchSource } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Button, EmptyState, ErrorState, Input, Select, Spinner } from '../../components'
import { useAction, useAsync } from '../../lib/hooks'
import { SearchResults } from './SearchResults'

export function SearchView({ onOpenNote, onGoSettings }: { onOpenNote: (noteId: string) => void; onGoSettings: () => void }) {
  const [query, setQuery] = useState('')
  const [folderId, setFolderId] = useState<string | null>(null)
  const [maxSources, setMaxSources] = useState(5)
  const [sources, setSources] = useState<SearchSource[]>()
  const [asked, setAsked] = useState('')
  const folders = useAsync(() => rpc('folders/list'), [])
  const act = useAction()

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q || act.busy) return
    const r = await act.run(() => rpc('search/query', { query: q, folderId, maxSources }))
    if (r) {
      setSources(r)
      setAsked(q)
    }
  }

  const noteCount = sources?.reduce((n, s) => n + s.notes.length, 0) ?? 0

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
        <Select aria-label="Số nguồn tối đa" value={String(maxSources)} onChange={(e) => setMaxSources(Number(e.target.value))}>
          <option value="5">Tối đa 5 nguồn</option>
          <option value="10">Tối đa 10 nguồn</option>
          <option value="20">Tối đa 20 nguồn</option>
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
      {!act.busy && sources?.length === 0 && (
        <EmptyState title="Không có nguồn/ghi chú đủ tin cậy">
          Thử diễn đạt khác, bỏ lọc thư mục, hoặc đợi ghi chú mới chuyển “Sẵn sàng tìm kiếm”.
        </EmptyState>
      )}
      {!!sources?.length && (
        <p className="muted" aria-live="polite">
          {sources.length} nguồn · {noteCount} ghi chú liên quan tới “{asked}” (tối đa {maxSources} nguồn)
        </p>
      )}
      {!!sources?.length && <SearchResults sources={sources} onOpenNote={onOpenNote} />}
    </section>
  )
}
