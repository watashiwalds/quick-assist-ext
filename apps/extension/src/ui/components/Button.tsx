import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'ghost' | 'danger' | 'link'

export function Button({
  variant = 'primary',
  size = 'md',
  busy = false,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md'; busy?: boolean }) {
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || busy}
      aria-busy={busy || undefined}
      className={`btn btn-${variant} btn-${size} ${className ?? ''}`}
    >
      {busy && <span className="spinner spinner-inline" aria-hidden />}
      {children}
    </button>
  )
}
