/** Tìm kiếm ngữ nghĩa (kịch bản #4, SDS §5.1.3). Owner UI: R04. */
import { type FormEvent, useState } from 'react'
import type { SearchHit } from '@/shared/api/types'
import { AppError, type SerializedError } from '@/shared/errors'
import { rpc } from '@/shared/messaging/client'
import { Button, EmptyState, ErrorState, Spinner } from '../../components'

export function SearchView() {
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<SearchHit[]>()
  const [error, setError] = useState<SerializedError>()
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(undefined)
    try {
      setHits(await rpc('search/query', { query: query.trim() }))
    } catch (err) {
      setError(err instanceof AppError ? err.toJSON() : { code: 'UNKNOWN', message: String(err), status: 0 })
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <form className="row" onSubmit={onSubmit}>
        <input
          aria-label="Câu hỏi tìm kiếm"
          placeholder="Bạn đang tìm điều gì?"
          value={query}
          maxLength={1000}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Button type="submit" disabled={loading}>
          Tìm
        </Button>
      </form>
      {loading && <Spinner label="Đang tìm nội dung tương đồng…" />}
      {error && <ErrorState error={error} />}
      {hits?.length === 0 && <EmptyState title="Không có kết quả phù hợp" />}
      <ul className="list">
        {hits?.map((h) => (
          <li key={h.chunk_id} className="card">
            <h3>{h.note_title ?? 'Ghi chú'}</h3>
            <div className="clamp">{h.text}</div>
            {h.note_url && (
              <a className="muted" href={h.note_url} target="_blank" rel="noreferrer noopener">
                Mở trang nguồn
              </a>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
