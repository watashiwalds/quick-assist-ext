/**
 * Kết quả tìm kiếm nhóm theo nguồn (Phase 2 — UX plan §5.2): tối đa 5 nhóm nguồn,
 * mỗi nhóm 3 ghi chú + "Xem thêm" (API trả tối đa 10 note/nguồn). Dùng chung cho
 * Thư viện (tab tìm gộp) và tab Tìm kiếm để không có hai cách hiển thị lệch nhau.
 */
import { useEffect, useState } from 'react'
import type { SearchNote, SearchSource } from '@/shared/api/types'
import { Button, ConfidenceBadge, GroupSection } from '../../components'

const INITIAL_NOTES = 3

const sourceKey = (s: SearchSource) => s.domain ?? '__unknown__'

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
    <div className="search-results" aria-label="Kết quả tìm kiếm theo nguồn">
      {sources.map((s) => {
        const key = sourceKey(s)
        const open = expanded.has(key)
        const visible = open ? s.notes : s.notes.slice(0, INITIAL_NOTES)
        const hiddenLoaded = s.notes.length - visible.length
        const beyondLoaded = Math.max(0, s.note_count - s.notes.length)
        return (
          <GroupSection
            key={key}
            label={s.label}
            count={s.note_count}
            collapsed={collapsed.has(key)}
            onToggle={() => setCollapsed((c) => toggle(c, key))}
          >
            <ol className="list hit-list">
              {visible.map((n) => (
                <SearchNoteCard key={n.note_id} note={n} onOpenNote={onOpenNote} />
              ))}
            </ol>
            {(hiddenLoaded > 0 || beyondLoaded > 0) && (
              <div className="source-group-more">
                {hiddenLoaded > 0 && (
                  <Button variant="ghost" size="sm" aria-expanded={open} onClick={() => setExpanded((e) => toggle(e, key))}>
                    {open ? 'Thu gọn' : `Xem thêm ${hiddenLoaded} ghi chú`}
                  </Button>
                )}
                {beyondLoaded > 0 && <small className="muted">và {beyondLoaded} ghi chú khác trong nguồn này</small>}
              </div>
            )}
          </GroupSection>
        )
      })}
    </div>
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
