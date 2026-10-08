import type { Note } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Button, StatusBadge } from '../../components'
import { formatDate } from '../../lib/hooks'
import { SummaryPanel } from '../summary/SummaryPanel'

export function NoteCard({
  note,
  folderName,
  selectMode,
  selected,
  onToggle,
  onEdit,
  onDelete,
  onChanged,
  onGoSettings,
  highlight,
}: {
  note: Note
  folderName?: string
  selectMode: boolean
  selected: boolean
  onToggle: () => void
  onEdit: () => void
  onDelete: () => void
  onChanged: (n: Note) => void
  onGoSettings: () => void
  highlight?: boolean
}) {
  const heading = note.title ?? note.domain ?? 'Ghi chú'
  return (
    <li className={`card ${highlight ? 'card-highlight' : ''}`} id={`note-${note.id}`} aria-label={heading}>
      <div className="row spread">
        <div className="row grow">
          {selectMode && <input type="checkbox" aria-label={`Chọn “${heading}”`} checked={selected} onChange={onToggle} />}
          <h3 className="grow">{heading}</h3>
        </div>
        <StatusBadge status={note.index_status} />
      </div>
      <div className="clamp">{note.content}</div>
      {note.summary_text && (
        <details className="saved-summary">
          <summary>Tóm tắt đã lưu</summary>
          <div className="prewrap">{note.summary_text}</div>
        </details>
      )}
      <div className="row muted meta">
        <span>{formatDate(note.created_at)}</span>
        {folderName && <span>· {folderName}</span>}
        {note.url && (
          <a href={note.url} target="_blank" rel="noreferrer noopener">
            · {note.domain ?? 'nguồn'}
          </a>
        )}
      </div>
      {!selectMode && (
        <div className="row wrap actions">
          <Button variant="ghost" size="sm" onClick={onEdit}>
            Sửa
          </Button>
          {(note.index_status === 'FAILED' || note.index_status === 'SKIPPED') && (
            <Button variant="ghost" size="sm" onClick={() => void rpc('notes/reindex', { id: note.id }).then(onChanged)}>
              Thử lại AI
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={onDelete}>
            Xoá
          </Button>
          <SummaryPanel note={note} onSaved={onChanged} onGoSettings={onGoSettings} />
        </div>
      )}
    </li>
  )
}
