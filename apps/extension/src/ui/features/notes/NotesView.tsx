/**
 * Thư viện ghi chú (C03 — kịch bản #3 + #5) — split-view theo W03:
 * rail thư mục | danh sách | reader/editor (thay modal editor).
 * Cache-first, lọc thư mục + từ khoá, xoá một/nhiều (xác nhận),
 * quản lý thư mục, ghi chú chưa gửi (N06).
 * Thanh tìm kiếm gộp cả tìm sâu AI (R04): gõ → lọc nhanh cục bộ, Enter → tìm kiếm ngữ nghĩa.
 */
import { type FormEvent, useEffect, useMemo, useState } from 'react'
import type { Note, SearchSource } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Button, ConfirmDialog, EmptyState, ErrorState, GroupSection, Icon, Input, PaneHeader, Select, Spinner, useToast } from '../../components'
import { useAction, useAsync, useBroadcast } from '../../lib/hooks'
import { SearchResults } from '../search/SearchResults'
import { countSearchNotes } from '../search/searchSummary'
import { FolderManager } from './FolderManager'
import { groupNotesBySource, type NoteEntry } from './groupNotes'
import { MoveNotesDialog } from './MoveNotesDialog'
import { NoteCard } from './NoteCard'
import { NoteReader } from './NoteReader'
import { PendingNotes } from './PendingNotes'

export function NotesView({ openNoteId, onOpened, onGoSettings }: { openNoteId?: string | null; onOpened?: () => void; onGoSettings: () => void }) {
  const [folderId, setFolderId] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [maxSources, setMaxSources] = useState(5)
  const [hits, setHits] = useState<SearchSource[] | null>(null)
  const [asked, setAsked] = useState('')
  const [selectMode, setSelectMode] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())
  const [active, setActive] = useState<Note | null>(null)
  const [confirmIds, setConfirmIds] = useState<string[] | null>(null)
  const [confirmUnits, setConfirmUnits] = useState(1)
  const [managing, setManaging] = useState(false)
  const [highlight, setHighlight] = useState<string | null>(null)
  const folders = useAsync(() => rpc('folders/list'), [])
  const notes = useAsync(() => rpc('notes/list', { folderId }), [folderId])
  const [moveOpen, setMoveOpen] = useState(false)
  const del = useAction()
  const move = useAction()
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
    const r = await search.run(() => rpc('search/query', { query: q, folderId, maxSources }))
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
  const resultNotes = useMemo(() => (hits ? countSearchNotes(hits) : 0), [hits])
  const groups = useMemo(() => {
    const list = notes.data ?? []
    const q = filter.trim().toLocaleLowerCase('vi')
    if (!q) return groupNotesBySource(list)
    // Lọc theo mục: part nào khớp cũng giữ toàn bộ tài liệu (nhãn/part 0 không bị mất).
    const hit = (n: Note) => `${n.title ?? ''} ${n.content} ${n.domain ?? ''}`.toLocaleLowerCase('vi').includes(q)
    const docHits = new Set(list.filter((n) => n.document_id && hit(n)).map((n) => n.document_id!))
    return groupNotesBySource(list.filter((n) => hit(n) || (n.document_id && docHits.has(n.document_id))))
  }, [notes.data, filter])
  const entries = useMemo(() => groups.flatMap((g) => g.entries), [groups])
  /** Số MỤC đã chọn trọn vẹn (tài liệu = 1 mục dù nhiều part). */
  const selectedUnits = useMemo(
    () => entries.filter((e) => e.notes.every((n) => selected.has(n.id))).length,
    [entries, selected],
  )
  const activeEntry = useMemo(
    () => entries.find((e) => e.notes.some((n) => n.id === active?.id)),
    [entries, active?.id],
  )

  const replace = (n: Note) => {
    notes.setData((notes.data ?? []).map((x) => (x.id === n.id ? n : x)).filter((x) => !folderId || x.folder_id === folderId))
    setActive((cur) => (cur?.id === n.id ? n : cur))
  }
  // Chọn/bỏ chọn một MỤC: tài liệu chọn tất cả part để xoá/chuyển đồng bộ.
  const toggleEntry = (entry: NoteEntry) =>
    setSelected((s) => {
      const all = entry.notes.every((n) => s.has(n.id))
      const next = new Set(s)
      for (const n of entry.notes) {
        if (all) next.delete(n.id)
        else next.add(n.id)
      }
      return next
    })
  // "Chọn cả nhóm": chọn/bỏ chọn đúng các note đang hiện trong nhóm — không tự move.
  const toggleGroup = (ids: string[]) =>
    setSelected((s) => {
      const allSelected = ids.every((id) => s.has(id))
      const next = new Set(s)
      for (const id of ids) {
        if (allSelected) next.delete(id)
        else next.add(id)
      }
      return next
    })

  const doMove = async (folderId: string | null) => {
    const ids = [...selected]
    if (ids.length === 0) return
    const r = await move.run(() => rpc('notes/move', { ids, folderId }))
    setMoveOpen(false)
    if (!r) return
    toast(`Đã chuyển ${r.moved} ghi chú`)
    if (r.missing.length > 0) toast(`${r.missing.length} ghi chú không còn tồn tại`, 'error')
    setSelected(new Set())
    setSelectMode(false)
    await notes.reload()
  }

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
      <aside className="folder-rail pane-rail" aria-label="Thư mục">
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
        <PaneHeader
          className="pane-head"
          title={showResults ? 'Kết quả tìm kiếm AI' : folderId ? (folderName.get(folderId) ?? 'Thư mục') : 'Tất cả ghi chú'}
          subtitle={
            showResults
              ? search.busy
                ? 'Đang tìm nội dung tương đồng…'
                : hits
                  ? `${hits.length} nguồn · ${resultNotes} ghi chú cho “${asked}”`
                  : ''
              : !notes.loading && !notes.error
                ? `${entries.length} mục`
                : undefined
          }
          actions={
            <>
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
            </>
          }
        />
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
              <Select className="topk-select" aria-label="Số nguồn tối đa" value={String(maxSources)} onChange={(e) => setMaxSources(Number(e.target.value))}>
                <option value="5">Tối đa 5 nguồn</option>
                <option value="10">Tối đa 10 nguồn</option>
                <option value="20">Tối đa 20 nguồn</option>
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
            <section aria-label="Kết quả tìm kiếm bằng AI">
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
                <EmptyState title="Không có nguồn/ghi chú đủ tin cậy">
                  Thử diễn đạt khác, bỏ lọc thư mục, hoặc đợi ghi chú mới chuyển “Sẵn sàng tìm kiếm”.
                </EmptyState>
              )}
              {!!hits?.length && <SearchResults sources={hits} onOpenNote={(id) => void openNoteById(id)} />}
            </section>
          ) : (
            <>
              <PendingNotes />
              {selectMode && (
                <div className="row spread selection-bar">
                  <span>Đã chọn {selectedUnits}</span>
                  <div className="row">
                    <Button size="sm" variant="ghost" onClick={() => setSelected(new Set(entries.flatMap((e) => e.notes.map((n) => n.id))))}>
                      Chọn tất cả
                    </Button>
                    <Button size="sm" variant="ghost" disabled={selected.size === 0} onClick={() => setMoveOpen(true)}>
                      Chuyển thư mục
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      disabled={selected.size === 0}
                      onClick={() => {
                        setConfirmUnits(selectedUnits)
                        setConfirmIds([...selected])
                      }}
                    >
                      Xoá ({selectedUnits})
                    </Button>
                  </div>
                </div>
              )}
              {(del.error || move.error) && <ErrorState error={(del.error ?? move.error)!} />}
              {notes.loading && !notes.data && <Spinner />}
              {notes.error && <ErrorState error={notes.error} onRetry={notes.reload} />}
              {notes.data?.length === 0 && (
                <EmptyState title="Chưa có ghi chú">Bôi đen văn bản trên trang → chuột phải → “Ghi chú văn bản này” (hoặc Alt+Shift+N).</EmptyState>
              )}
              {!!notes.data?.length && entries.length === 0 && <EmptyState title="Không có ghi chú khớp bộ lọc" />}
              <div className="note-groups">
                {groups.map((g) => {
                  const key = g.key
                  const ids = g.notes.map((n) => n.id)
                  const allSelected = ids.length > 0 && ids.every((id) => selected.has(id))
                  const isDoc = g.kind === 'document'
                  return (
                    <GroupSection
                      key={key}
                      label={g.label}
                      count={isDoc ? g.notes.length : g.entries.length}
                      countLabel={isDoc ? `${g.notes.length} phần` : undefined}
                      ariaLabel={isDoc ? `Tài liệu ${g.label}` : undefined}
                      summary={g.summary}
                      collapsed={collapsedGroups.has(key)}
                      onToggle={() =>
                        setCollapsedGroups((s) => (s.has(key) ? (s.delete(key), new Set(s)) : new Set(s.add(key))))
                      }
                      actions={
                        selectMode ? (
                          <Button variant="ghost" size="sm" aria-pressed={allSelected} onClick={() => toggleGroup(ids)}>
                            {allSelected ? 'Bỏ chọn nhóm' : 'Chọn cả nhóm'}
                          </Button>
                        ) : undefined
                      }
                    >
                      <ul className="note-list">
                        {g.entries.map((entry) => {
                          const n = entry.note
                          const entryIds = entry.notes.map((x) => x.id)
                          return (
                            <NoteCard
                              key={entry.key}
                              note={n}
                              folderName={folderId ? undefined : folderName.get(n.folder_id)}
                              selectMode={selectMode}
                              selected={entryIds.every((id) => selected.has(id))}
                              active={!!active?.id && entryIds.includes(active.id)}
                              highlight={!!highlight && entryIds.includes(highlight)}
                              onToggle={() => toggleEntry(entry)}
                              onOpen={() => setActive(n)}
                            />
                          )
                        })}
                      </ul>
                    </GroupSection>
                  )
                })}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="reader-pane">
        <NoteReader
          note={active}
          parts={activeEntry?.notes}
          folders={folders.data ?? []}
          onClose={() => setActive(null)}
          onSaved={replace}
          onDelete={(n) => {
            const e = entries.find((x) => x.notes.some((p) => p.id === n.id))
            setConfirmUnits(1)
            setConfirmIds(e ? e.notes.map((p) => p.id) : [n.id])
          }}
          onGoSettings={onGoSettings}
        />
      </div>

      <FolderManager open={managing} folders={folders.data ?? []} onClose={() => setManaging(false)} onChanged={() => void folders.reload().then(notes.reload)} />
      <MoveNotesDialog
        open={moveOpen}
        count={selectedUnits}
        folders={folders.data ?? []}
        busy={move.busy}
        onCancel={() => setMoveOpen(false)}
        onConfirm={(id) => void doMove(id)}
      />
      <ConfirmDialog
        open={!!confirmIds}
        title={confirmUnits > 1 ? `Xoá ${confirmUnits} mục?` : 'Xoá ghi chú?'}
        message={
          confirmIds && confirmIds.length > 1
            ? 'Mục đã chọn (gồm mọi phần của tài liệu) sẽ bị xoá khỏi thư viện và kết quả tìm kiếm trên mọi thiết bị.'
            : 'Ghi chú sẽ bị xoá khỏi thư viện và kết quả tìm kiếm trên mọi thiết bị.'
        }
        confirmLabel="Xoá"
        danger
        busy={del.busy}
        onCancel={() => setConfirmIds(null)}
        onConfirm={() => void doDelete(confirmIds ?? [])}
      />
    </section>
  )
}
