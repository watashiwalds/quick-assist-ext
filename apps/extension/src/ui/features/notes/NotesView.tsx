/**
 * Thư viện ghi chú (C03 — kịch bản #3 + #5) — split-view theo W03:
 * rail thư mục | danh sách | reader/editor (thay modal editor).
 * Cache-first, lọc thư mục + từ khoá, xoá một/nhiều (xác nhận),
 * quản lý thư mục, ghi chú chưa gửi (N06).
 * Thanh tìm kiếm gộp cả tìm sâu AI (R04): gõ → lọc nhanh cục bộ, Enter → tìm kiếm ngữ nghĩa.
 */
import { type FormEvent, useEffect, useMemo, useState } from 'react'
import type { Note, SearchHit } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Button, ConfirmDialog, EmptyState, ErrorState, Icon, Input, Select, Spinner, useToast } from '../../components'
import { useAction, useAsync, useBroadcast } from '../../lib/hooks'
import { FolderManager } from './FolderManager'
import { NoteCard } from './NoteCard'
import { NoteReader } from './NoteReader'
import { PendingNotes } from './PendingNotes'

export function NotesView({ openNoteId, onOpened, onGoSettings }: { openNoteId?: string | null; onOpened?: () => void; onGoSettings: () => void }) {
  const [folderId, setFolderId] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [topK, setTopK] = useState(5)
  const [hits, setHits] = useState<SearchHit[] | null>(null)
  const [asked, setAsked] = useState('')
  const [selectMode, setSelectMode] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [active, setActive] = useState<Note | null>(null)
  const [confirmIds, setConfirmIds] = useState<string[] | null>(null)
  const [managing, setManaging] = useState(false)
  const [highlight, setHighlight] = useState<string | null>(null)
  const folders = useAsync(() => rpc('folders/list'), [])
  const notes = useAsync(() => rpc('notes/list', { folderId }), [folderId])
  const del = useAction()
  const search = useAction()
  const toast = useToast()
  useBroadcast((e) => {
    if (e.type === 'notes/changed') void notes.reload()
    if (e.type === 'folders/changed') void folders.reload()
  })

  // Mở ghi chú (từ kết quả tìm kiếm AI hoặc được chọn ở tab khác) — chế độ đọc, highlight hàng tương ứng.
  const openNoteById = (id: string) =>
    rpc('notes/get', { id })
      .then((n) => {
        setFolderId(null)
        setHighlight(n.id)
        setActive(n)
      })
      .catch(() => toast('Ghi chú không còn tồn tại', 'error'))
  useEffect(() => {
    if (!openNoteId) return
    void openNoteById(openNoteId).finally(() => onOpened?.())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openNoteId])

  // Tìm sâu bằng AI (R04) với chính từ khoá đang gõ + thư mục đang chọn; kết quả thay vùng danh sách.
  const showResults = !!hits || search.busy || !!search.error
  async function runSearch(e?: FormEvent) {
    e?.preventDefault()
    const q = filter.trim()
    if (!q || search.busy) return
    const r = await search.run(() => rpc('search/query', { query: q, folderId, topK }))
    if (r) {
      setHits(r)
      setAsked(q)
    }
  }
  const exitResults = () => {
    setHits(null)
    search.clearError()
  }
  // Gõ tiếp sau khi có kết quả AI → quay về chế độ lọc nhanh cục bộ.
  const changeFilter = (v: string) => {
    setFilter(v)
    if (showResults) exitResults()
  }
  // Đổi thư mục (rail hoặc ô chọn) cũng làm mới kết quả AI cũ.
  const changeFolder = (id: string | null) => {
    setFolderId(id)
    if (showResults) exitResults()
  }

  const folderName = useMemo(() => new Map((folders.data ?? []).map((f) => [f.id, f.name])), [folders.data])
  const visible = useMemo(() => {
    const q = filter.trim().toLocaleLowerCase('vi')
    const list = notes.data ?? []
    if (!q) return list
    return list.filter((n) => `${n.title ?? ''} ${n.content} ${n.domain ?? ''}`.toLocaleLowerCase('vi').includes(q))
  }, [notes.data, filter])

  const replace = (n: Note) => {
    notes.setData((notes.data ?? []).map((x) => (x.id === n.id ? n : x)).filter((x) => !folderId || x.folder_id === folderId))
    setActive((cur) => (cur?.id === n.id ? n : cur))
  }
  const toggle = (id: string) => setSelected((s) => (s.has(id) ? (s.delete(id), new Set(s)) : new Set(s.add(id))))

  const doDelete = async (ids: string[]) => {
    const r = await del.run(() => rpc('notes/delete', { ids }))
    setConfirmIds(null)
    if (!r) return
    toast(`Đã xoá ${r.deleted} ghi chú`)
    setSelected(new Set())
    setSelectMode(false)
    setActive((cur) => (cur && ids.includes(cur.id) ? null : cur))
    notes.setData((notes.data ?? []).filter((n) => !ids.includes(n.id)))
  }

  return (
    <section className={`library${active ? ' has-active' : ''}`} aria-label="Thư viện ghi chú">
      <aside className="folder-rail" aria-label="Thư mục">
        <div className="rail-head">
          <h2 className="rail-title">Thư mục</h2>
        </div>
        <nav className="folder-nav" aria-label="Danh sách thư mục">
          <a
            className={`folder-item${folderId === null ? ' is-active' : ''}`}
            href="#"
            aria-current={folderId === null || undefined}
            onClick={(e) => {
              e.preventDefault()
              changeFolder(null)
            }}
          >
            <Icon name="layers" size={15} />
            <span className="folder-label">Tất cả ghi chú</span>
          </a>
          <div className="rail-divider" role="separator" />
          {(folders.data ?? []).map((f) => (
            <a
              key={f.id}
              className={`folder-item${folderId === f.id ? ' is-active' : ''}`}
              href="#"
              aria-current={folderId === f.id || undefined}
              onClick={(e) => {
                e.preventDefault()
                changeFolder(f.id)
              }}
            >
              <Icon name="folder" size={15} />
              <span className="folder-label">{f.name}</span>
            </a>
          ))}
        </nav>
        <div className="rail-foot">
          <Button variant="ghost" size="sm" className="rail-action" onClick={() => setManaging(true)} title="Tạo thư mục mới">
            <Icon name="plus" size={15} />
            Thêm thư mục
          </Button>
          <Button variant="ghost" size="sm" className="rail-action" onClick={() => setManaging(true)} title="Tạo, đổi tên, xoá thư mục">
            <Icon name="folder" size={15} />
            Quản lý thư mục
          </Button>
          <p className="rail-hint">
            Mẹo: nhấn <kbd>Alt</kbd> + <kbd>Shift</kbd> + <kbd>N</kbd> để ghi chú nhanh.
          </p>
        </div>
      </aside>

      <div className="notes-pane" aria-label="Danh sách ghi chú">
        <div className="pane-head">
          <div className="pane-heading">
            <h2 className="pane-title">
              {showResults ? 'Kết quả tìm kiếm AI' : folderId ? (folderName.get(folderId) ?? 'Thư mục') : 'Tất cả ghi chú'}
            </h2>
            {showResults ? (
              <p className="pane-subtitle" aria-live="polite">
                {search.busy ? 'Đang tìm nội dung tương đồng…' : hits ? `${hits.length} kết quả cho “${asked}”` : ''}
              </p>
            ) : (
              !notes.loading && !notes.error && <p className="pane-subtitle">{visible.length} ghi chú</p>
            )}
          </div>
          <div className="pane-actions">
            <Button variant="ghost" size="sm" aria-pressed={selectMode} onClick={() => (setSelectMode(!selectMode), setSelected(new Set()))}>
              <Icon name="check-square" size={15} />
              {selectMode ? 'Xong' : 'Chọn'}
            </Button>
            <Button variant="ghost" size="sm" title="Đồng bộ với máy chủ" aria-label="Đồng bộ" onClick={() => void rpc('notes/sync').then(notes.reload)}>
              <Icon name="sync" size={15} />
            </Button>
            <Button variant="ghost" size="sm" aria-label="Thư mục" title="Tạo, đổi tên, xoá thư mục" onClick={() => setManaging(true)}>
              <Icon name="folder" size={15} />
            </Button>
          </div>
        </div>
        <div className="pane-tools">
          <form role="search" onSubmit={(e) => void runSearch(e)}>
            <div className="search-row">
              <label className="search">
                <Icon name="search" size={14} />
                <Input
                  type="search"
                  aria-label="Tìm kiếm hoặc lọc ghi chú"
                  placeholder="Lọc nhanh trong thư viện…"
                  value={filter}
                  maxLength={1000}
                  onChange={(e) => changeFilter(e.target.value)}
                />
              </label>
              <Select className="topk-select" aria-label="Số kết quả tối đa" value={String(topK)} onChange={(e) => setTopK(Number(e.target.value))}>
                <option value="5">Tối đa 5</option>
                <option value="10">Tối đa 10</option>
                <option value="20">Tối đa 20</option>
              </Select>
            </div>
            <small className="search-hint">
              Gõ để lọc nhanh trong thư viện · Nhấn <kbd>Enter</kbd> để tìm sâu bằng AI (có thể gõ không dấu).
            </small>
          </form>
          <Select
            className="folder-select"
            aria-label="Lọc theo thư mục"
            value={folderId ?? ''}
            onChange={(e) => changeFolder(e.target.value || null)}
          >
            <option value="">Tất cả thư mục</option>
            {folders.data?.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="pane-scroll">
          {showResults ? (
            <div aria-label="Kết quả tìm kiếm bằng AI">
              <div className="results-head">
                <Button variant="ghost" size="sm" onClick={exitResults}>
                  ← Về danh sách
                </Button>
              </div>
              {search.busy && <Spinner label="Đang tìm nội dung tương đồng cho bạn…" />}
              {search.error && (
                <ErrorState
                  error={search.error}
                  action={
                    search.error.code === 'QUOTA_EXCEEDED' ? (
                      <Button variant="link" size="sm" onClick={onGoSettings}>
                        Xem hạn mức
                      </Button>
                    ) : undefined
                  }
                />
              )}
              {!search.busy && hits?.length === 0 && (
                <EmptyState title="Không có kết quả phù hợp">Thử diễn đạt khác, bỏ lọc thư mục, hoặc đợi ghi chú mới chuyển “Sẵn sàng tìm kiếm”.</EmptyState>
              )}
              <ol className="list hit-list">
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
                      <Button variant="ghost" size="sm" onClick={() => void openNoteById(h.note_id)}>
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
            </div>
          ) : (
            <>
              <PendingNotes />
              {selectMode && (
                <div className="row spread selection-bar">
                  <span>Đã chọn {selected.size}</span>
                  <div className="row">
                    <Button size="sm" variant="ghost" onClick={() => setSelected(new Set(visible.map((n) => n.id)))}>
                      Chọn tất cả
                    </Button>
                    <Button size="sm" variant="danger" disabled={selected.size === 0} onClick={() => setConfirmIds([...selected])}>
                      Xoá ({selected.size})
                    </Button>
                  </div>
                </div>
              )}
              {del.error && <ErrorState error={del.error} />}
              {notes.loading && !notes.data && <Spinner />}
              {notes.error && <ErrorState error={notes.error} onRetry={notes.reload} />}
              {notes.data?.length === 0 && (
                <EmptyState title="Chưa có ghi chú">Bôi đen văn bản trên trang → chuột phải → “Ghi chú văn bản này” (hoặc Alt+Shift+N).</EmptyState>
              )}
              {!!notes.data?.length && visible.length === 0 && <EmptyState title="Không có ghi chú khớp bộ lọc" />}
              <ul className="note-list" aria-live="polite">
                {visible.map((n) => (
                  <NoteCard
                    key={n.id}
                    note={n}
                    folderName={folderId ? undefined : folderName.get(n.folder_id)}
                    selectMode={selectMode}
                    selected={selected.has(n.id)}
                    active={active?.id === n.id}
                    highlight={highlight === n.id}
                    onToggle={() => toggle(n.id)}
                    onOpen={() => setActive(n)}
                  />
                ))}
              </ul>
            </>
          )}
        </div>
      </div>

      <div className="reader-pane">
        <NoteReader
          note={active}
          folders={folders.data ?? []}
          onClose={() => setActive(null)}
          onSaved={replace}
          onDelete={(n) => setConfirmIds([n.id])}
          onGoSettings={onGoSettings}
        />
      </div>

      <FolderManager open={managing} folders={folders.data ?? []} onClose={() => setManaging(false)} onChanged={() => void folders.reload().then(notes.reload)} />
      <ConfirmDialog
        open={!!confirmIds}
        title={confirmIds && confirmIds.length > 1 ? `Xoá ${confirmIds.length} ghi chú?` : 'Xoá ghi chú?'}
        message="Ghi chú sẽ bị xoá khỏi thư viện và kết quả tìm kiếm trên mọi thiết bị."
        confirmLabel="Xoá"
        danger
        busy={del.busy}
        onCancel={() => setConfirmIds(null)}
        onConfirm={() => void doDelete(confirmIds ?? [])}
      />
    </section>
  )
}
