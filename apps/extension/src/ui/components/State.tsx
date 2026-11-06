import type { ReactNode } from 'react'
import { type SerializedError, userMessage } from '@/shared/errors'
import { Button } from './Button'

export function Spinner({ label = 'Đang tải…' }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden /> {label}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state">
      <strong>{title}</strong>
      {children && <div className="muted">{children}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry, action }: { error: SerializedError; onRetry?: () => void; action?: ReactNode }) {
  return (
    <div className="state error" role="alert">
      <span>{userMessage(error)}</span>
      <div className="row">
        {onRetry && (
          <Button variant="ghost" size="sm" onClick={onRetry}>
            Thử lại
          </Button>
        )}
        {action}
      </div>
      {error.requestId && <small className="muted">Mã lỗi: {error.requestId}</small>}
    </div>
  )
}

/** Thông báo dạng dải (không chặn thao tác). */
export function Banner({ tone = 'info', children }: { tone?: 'info' | 'warn' | 'error' | 'ok'; children: ReactNode }) {
  return (
    <div className={`banner banner-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}

const STATUS_LABEL: Record<string, { text: string; hint: string }> = {
  PROCESSING: { text: 'Đang xử lý', hint: 'AI đang tạo chỉ mục tìm kiếm, sẽ xong sau vài giây' },
  READY: { text: 'Sẵn sàng tìm kiếm', hint: 'Ghi chú đã tìm được theo ngữ nghĩa' },
  SKIPPED: { text: 'Bỏ qua (hết quota)', hint: 'Hết hạn mức AI nên chưa tạo chỉ mục — ghi chú vẫn được lưu' },
  FAILED: { text: 'Lỗi xử lý AI', hint: 'Tạo chỉ mục thất bại — bấm “Thử lại AI”' },
}

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS_LABEL[status] ?? { text: status, hint: '' }
  return (
    <span className={`badge badge-${status.toLowerCase()}`} title={s.hint}>
      {s.text}
    </span>
  )
}

export function ProgressBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0
  const tone = pct >= 90 ? 'danger' : pct >= 70 ? 'warn' : 'ok'
  return (
    <div className="progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
      <div className={`progress-bar progress-${tone}`} style={{ width: `${pct}%` }} />
    </div>
  )
}
