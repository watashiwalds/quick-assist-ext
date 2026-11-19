/**
 * PaneHeader — phần đầu của một pane: tiêu đề, phụ đề (aria-live) và cụm hành động.
 * Dùng chung cho Thư viện (`.pane-head`) và Tìm trong trang (`.pf-head`); class truyền vào
 * để giữ nguyên giao diện cũ trong giai đoạn chuyển tiếp.
 *
 * `children` nằm trên hàng tiêu đề (vd. banner cảnh báo), `actions` nằm bên phải.
 */
import type { ElementType, ReactNode } from 'react'

export function PaneHeader({
  title,
  subtitle,
  actions,
  children,
  footer,
  as: Tag = 'div',
  className = '',
  rowClassName = '',
  headingClassName = '',
  titleClassName = '',
  subtitleClassName = '',
  actionsClassName = '',
  subtitleLive = true,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  /** Nội dung đứng trước hàng tiêu đề (banner, thông báo). */
  children?: ReactNode
  /** Nội dung dưới hàng tiêu đề (ghi chú, hint). */
  footer?: ReactNode
  as?: ElementType
  className?: string
  rowClassName?: string
  headingClassName?: string
  titleClassName?: string
  subtitleClassName?: string
  actionsClassName?: string
  /** Phụ đề cập nhật theo thời gian thực (mặc định bật cho số lượng kết quả). */
  subtitleLive?: boolean
}) {
  return (
    <Tag className={className || undefined}>
      {children}
      <div className={rowClassName || undefined}>
        <div className={headingClassName || undefined}>
          <h2 className={titleClassName || undefined}>{title}</h2>
          {subtitle != null && subtitle !== '' && (
            <p className={subtitleClassName || undefined} aria-live={subtitleLive ? 'polite' : undefined}>
              {subtitle}
            </p>
          )}
        </div>
        {actions != null && <div className={actionsClassName || undefined}>{actions}</div>}
      </div>
      {footer}
    </Tag>
  )
}
