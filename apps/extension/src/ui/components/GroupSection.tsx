/**
 * GroupSection — nhóm kết quả theo NGUỒN (Phase 2 — UX plan §5.2, dùng chung từ Phase 5):
 * header domain + số ghi chú, tóm tắt ghép từ ghi chú (không gọi AI), có thể mở/đóng
 * bằng bàn phím (`aria-expanded` + `aria-controls`). Thư viện và tab Tìm kiếm cùng dùng.
 */
import { type ReactNode, useId } from 'react'
import { Icon } from './Icon'

export function GroupSection({
  label,
  count,
  summary,
  collapsed,
  onToggle,
  actions,
  children,
}: {
  label: string
  count: number
  /** Tóm tắt từ ghi chú trong nhóm (đã cắt ngắn) — chỉ Thư viện dùng. */
  summary?: string | null
  collapsed: boolean
  onToggle: () => void
  /** Nút thao tác cạnh header (vd. "Chọn cả nhóm"). */
  actions?: ReactNode
  children: ReactNode
}) {
  const bodyId = useId()
  return (
    <section className="source-group" aria-label={`Nguồn ${label}`}>
      <div className="source-group-head">
        <button
          type="button"
          className="source-group-toggle"
          aria-expanded={!collapsed}
          aria-controls={bodyId}
          onClick={onToggle}
        >
          <Icon name={collapsed ? 'chevron-right' : 'chevron-down'} size={14} />
          <span className="source-group-label" title={label}>
            {label}
          </span>
          <span className="source-group-count">{count} ghi chú</span>
        </button>
        {actions && <div className="source-group-actions">{actions}</div>}
      </div>
      {summary && (
        <p className="source-group-summary">
          <span className="note-item-badge">Tóm tắt từ ghi chú</span>
          {summary}
        </p>
      )}
      <div id={bodyId} hidden={collapsed}>
        {children}
      </div>
    </section>
  )
}
