/**
 * Design system tối thiểu (task A05 — owner UI/UX). Mọi màn hình dùng chung các
 * component này để trạng thái loading/empty/error nhất quán (NFR khả năng sử dụng).
 */
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { type SerializedError, userMessage } from '@/shared/errors'

export function Button({
  variant = 'primary',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'danger' }) {
  return <button {...props} className={`btn btn-${variant} ${props.className ?? ''}`} />
}

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

export function ErrorState({ error, onRetry }: { error: SerializedError; onRetry?: () => void }) {
  return (
    <div className="state error" role="alert">
      <span>{userMessage(error)}</span>
      {onRetry && (
        <Button variant="ghost" onClick={onRetry}>
          Thử lại
        </Button>
      )}
      {error.requestId && <small className="muted">Mã lỗi: {error.requestId}</small>}
    </div>
  )
}

const STATUS_LABEL: Record<string, string> = {
  PROCESSING: 'Đang xử lý',
  READY: 'Sẵn sàng tìm kiếm',
  SKIPPED: 'Bỏ qua (hết quota)',
  FAILED: 'Lỗi xử lý AI',
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{STATUS_LABEL[status] ?? status}</span>
}
