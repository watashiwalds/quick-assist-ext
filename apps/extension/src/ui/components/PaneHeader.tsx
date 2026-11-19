/**
 * PaneHeader — phần đầu của một pane: tiêu đề, phụ đề (aria-live) và cụm hành động.
 * Dùng chung cho Thư viện (`.pane-head`) và Tìm trong trang (`.pf-head`): chỉ class ngoài truyền vào,
 * markup nội bộ cố định (`.pane-head-row` / `.pane-heading` / `.pane-title` / `.pane-subtitle` /
 * `.pane-actions`); CSS `.pf-*` cũ giữ làm alias 1 nhịp trong giai đoạn chuyển tiếp.
 *
 * `children` nằm trên hàng tiêu đề (vd. banner cảnh báo), `actions` nằm bên phải,
 * `footer` nằm dưới hàng tiêu đề (vd. hàng hint của Tìm trong trang).
 */
import type { ElementType, ReactNode } from 'react'

export function PaneHeader({
  title,
  subtitle,
  actions,
  children,
  footer,
  as: Tag = 'div',
  className,
  subtitleLive = true,
  id,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  /** Nội dung đứng trước hàng tiêu đề (banner, thông báo). */
  children?: ReactNode
  /** Nội dung dưới hàng tiêu đề (hint, liên kết phụ). */
  footer?: ReactNode
  as?: ElementType
  className?: string
  /** Phụ đề cập nhật theo thời gian thực (mặc định bật cho số lượng kết quả). */
  subtitleLive?: boolean
  id?: string
}) {
  return (
    <Tag id={id} className={className || undefined}>
      {children}
      <div className="pane-head-row">
        <div className="pane-heading">
          <h2 className="pane-title">{title}</h2>
          {subtitle != null && subtitle !== '' && (
            <p className="pane-subtitle" aria-live={subtitleLive ? 'polite' : undefined}>
              {subtitle}
            </p>
          )}
        </div>
        {actions != null && <div className="pane-actions">{actions}</div>}
      </div>
      {footer}
    </Tag>
  )
}
