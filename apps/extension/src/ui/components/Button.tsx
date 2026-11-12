import type { ButtonHTMLAttributes, Ref } from 'react'

type Variant = 'primary' | 'ghost' | 'soft' | 'danger' | 'danger-ghost' | 'link'

export function Button({
  variant = 'primary',
  size = 'md',
  busy = false,
  className,
  children,
  ref,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md'; busy?: boolean; ref?: Ref<HTMLButtonElement> }) {
  return (
    <button
      type="button"
      ref={ref}
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
