/**
 * Hàng ghi chú trong danh sách (W03): tiêu đề + trích đoạn + ngày/thư mục + trạng thái.
 * Bấm hàng → mở reader; ở chế độ chọn, hàng trở thành checkbox (bấm cả hàng để chọn).
 * Thao tác (Sửa/Xoá/Tóm tắt/Thử lại AI) nằm ở reader — xem NoteReader.
 */
import type { Note } from '@/shared/api/types'
import { StatusBadge } from '../../components'
import { formatDate } from '../../lib/hooks'

export function NoteCard({
  note,
  folderName,
  selectMode,
  selected,
  active,
  highlight,
  onToggle,
  onOpen,
}: {
  note: Note
  folderName?: string
  selectMode: boolean
  selected: boolean
  active?: boolean
  highlight?: boolean
  onToggle: () => void
  onOpen: () => void
}) {
  const heading = note.title ?? note.domain ?? 'Ghi chú'
  const body = (
    <div className="note-item-body">
      <h3 className="note-item-title">{heading}</h3>
      <div className="note-item-excerpt">{note.content}</div>
      <div className="note-item-meta">
        <span>{formatDate(note.created_at)}</span>
        {folderName && (
          <>
            <span className="meta-dot" aria-hidden />
            <span>{folderName}</span>
          </>
        )}
        <StatusBadge status={note.index_status} />
      </div>
    </div>
  )
  return (
    <li className={`note-row${highlight ? ' note-row-highlight' : ''}`} id={`note-${note.id}`} aria-label={heading}>
      {selectMode ? (
        <div
          className="note-item"
          onClick={onToggle}
          role="presentation"
        >
          <input
            type="checkbox"
            aria-label={`Chọn “${heading}”`}
            checked={selected}
            onClick={(e) => e.stopPropagation()}
            onChange={onToggle}
          />
          {body}
        </div>
      ) : (
        <a
          className={`note-item${active ? ' is-active' : ''}`}
          href="#"
          onClick={(e) => {
            e.preventDefault()
            onOpen()
          }}
        >
          {body}
        </a>
      )}
    </li>
  )
}
