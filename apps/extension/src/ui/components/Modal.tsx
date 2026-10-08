/**
 * Hộp thoại có bẫy focus (Tab không thoát ra ngoài), Esc để đóng, trả focus về nút đã mở
 * — WCAG 2.1 (A05). Dùng <dialog> gốc của trình duyệt để có sẵn ngữ nghĩa modal.
 */
import { type ReactNode, useEffect, useId, useRef, useState } from 'react'
import { Button } from './Button'
import { Field, Input } from './Form'

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId() // id riêng mỗi hộp thoại (hộp thoại lồng nhau không trùng id)
  useEffect(() => {
    const d = ref.current
    if (!open || !d) return
    const opener = document.activeElement as HTMLElement | null
    if (!d.open) {
      if (typeof d.showModal === 'function') d.showModal()
      else d.setAttribute('open', '') // môi trường test không có showModal
    }
    d.querySelector<HTMLElement>('[data-autofocus], input, textarea, select, .modal-body button')?.focus()
    return () => opener?.focus?.() // trả focus về nút đã mở hộp thoại
  }, [open])
  if (!open) return null
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.preventDefault()
          onClose()
        }
        if (e.key !== 'Tab') return
        const nodes = Array.from(
          e.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), input, textarea, select, a[href]'),
        )
        if (nodes.length === 0) return
        const first = nodes[0]!
        const last = nodes[nodes.length - 1]!
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }}
    >
      <header className="modal-head">
        <h2 id={titleId}>{title}</h2>
        <Button variant="ghost" size="sm" aria-label="Đóng" onClick={onClose}>
          ✕
        </Button>
      </header>
      <div className="modal-body">{children}</div>
      {footer && <footer className="modal-foot">{footer}</footer>}
    </dialog>
  )
}

/**
 * Xác nhận thao tác nguy hiểm. `confirmText` (vd "XOÁ") bắt người dùng gõ lại → xác nhận 2 bước.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Xác nhận',
  danger = false,
  confirmText,
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean
  title: string
  message: ReactNode
  confirmLabel?: string
  danger?: boolean
  confirmText?: string
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const [typed, setTyped] = useState('')
  useEffect(() => setTyped(''), [open])
  const ok = !confirmText || typed.trim().toUpperCase() === confirmText.toUpperCase()
  return (
    <Modal
      open={open}
      title={title}
      onClose={onCancel}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel} disabled={busy}>
            Huỷ
          </Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} disabled={!ok} busy={busy}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="stack">
        <div>{message}</div>
        {confirmText && (
          <Field label={`Gõ “${confirmText}” để xác nhận`}>
            {(id) => <Input id={id} value={typed} autoComplete="off" onChange={(e) => setTyped(e.target.value)} />}
          </Field>
        )}
      </div>
    </Modal>
  )
}
