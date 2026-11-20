/**
 * Kết quả tìm kiếm nhóm theo nguồn (Phase 2 — UX plan §5.2): tối đa 5 nhóm nguồn,
 * mỗi nhóm 3 ghi chú + "Xem thêm" (API trả tối đa 10 note/nguồn). Dùng chung cho
 * Thư viện (tab tìm gộp) và tab Tìm kiếm để không có hai cách hiển thị lệch nhau.
 * ADR-0018: trong mỗi nhóm domain, các note có URL khác nhau gom thành NHÓM CON theo
 * TRANG (raw URL bỏ query/hash); chỉ hiện header trang khi nhóm có > 1 trang.
 */
import { useEffect, useState } from 'react'
import type { SearchNote, SearchSource } from '@/shared/api/types'
import { groupByPage } from '@/shared/source'
import { Button, ConfidenceBadge, GroupSection } from '../../components'

const INITIAL_NOTES = 3

/** Khoá nhóm nguồn: document_id tránh trùng key khi hai tài liệu khác nhau cùng domain. */
const sourceKey = (s: SearchSource) => s.document_id ?? s.domain ?? '__unknown__'

export function SearchResults({
  sources,
  onOpenNote,
}: {
  sources: SearchSource[]
  onOpenNote: (noteId: string) => void
}) {
  // Đổi truy vấn → reset trạng thái mở/đóng của nhóm.
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  useEffect(() => {
    setExpanded(new Set())
    setCollapsed(new Set())
  }, [sources])

  const toggle = (set: Set<string>, key: string) => {
    const next = new Set(set)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    return next
  }

  return (
    <section className="search-results" aria-label="Kết quả tìm kiếm theo nguồn">
      {sources.map((s) => {
        const key = sourceKey(s)
        const open = expanded.has(key)
        const visible = open ? s.notes : s.notes.slice(0, INITIAL_NOTES)
        const hiddenLoaded = s.notes.length - visible.length
        const beyondLoaded = Math.max(0, s.note_count - s.notes.length)
        const pages = groupByPage(visible)
        return (
          <GroupSection
            key={key}
            bodyId={`search-group-${key}-body`}
            label={s.label}
            count={s.note_count}
            collapsed={collapsed.has(key)}
            onToggle={() => setCollapsed((c) => toggle(c, key))}
          >
            {pages.length <= 1 ? (
              <ol className="list hit-list">
                {visible.map((n) => (
                  <SearchNoteCard key={n.note_id} note={n} onOpenNote={onOpenNote} />
                ))}
              </ol>
            ) : (
              pages.map((p) => (
                <section key={p.key} className="source-page" aria-label={`Trang ${p.label}`}>
                  <p className="source-page-head">
                    {p.url ? (
                      <a className="source-page-label" href={p.url} target="_blank" rel="noreferrer noopener" title={p.url}>
                        {p.label}
                      </a>
                    ) : (
                      <span className="source-page-label">{p.label}</span>
                    )}
                    <span className="source-page-count">{p.items.length} ghi chú</span>
                  </p>
                  <ol className="list hit-list">
                    {p.items.map((n) => (
                      <SearchNoteCard key={n.note_id} note={n} onOpenNote={onOpenNote} />
                    ))}
                  </ol>
                </section>
              ))
            )}
            {(hiddenLoaded > 0 || beyondLoaded > 0) && (
              <div className="source-group-more">
                {hiddenLoaded > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-expanded={open}
                    aria-controls={`search-group-${key}-body`}
                    onClick={() => setExpanded((e) => toggle(e, key))}
                  >
                    {open ? 'Thu gọn' : `Xem thêm ${hiddenLoaded} ghi chú`}
                  </Button>
                )}
                {beyondLoaded > 0 && <small className="muted">và {beyondLoaded} ghi chú khác trong nguồn này</small>}
              </div>
            )}
          </GroupSection>
        )
      })}
    </section>
  )
}

function SearchNoteCard({ note, onOpenNote }: { note: SearchNote; onOpenNote: (noteId: string) => void }) {
  return (
    <li className="card">
      <div className="row spread">
        <h3 className="grow">{note.title ?? 'Ghi chú'}</h3>
        <ConfidenceBadge value={note.similarity} kind="similarity" />
      </div>
      {note.summary ? (
        <div className="clamp">
          <span className="note-item-badge">Tóm tắt</span>
          {note.summary}
        </div>
      ) : (
        <div className="clamp">{note.snippet}</div>
      )}
      <div className="row actions">
        <Button variant="ghost" size="sm" onClick={() => onOpenNote(note.note_id)}>
          Mở ghi chú
        </Button>
        {note.url && (
          <a className="btn btn-ghost btn-sm" href={note.url} target="_blank" rel="noreferrer noopener">
            Mở trang nguồn ↗
          </a>
        )}
      </div>
    </li>
  )
}
