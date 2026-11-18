import { type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes, useId } from 'react'

export function Field({
  label,
  hint,
  help,
  error,
  children,
}: {
  label: string
  hint?: string
  /** Dòng mô tả ngay dưới nhãn (trước ô nhập), dùng khi hint cuối field chưa đủ. */
  help?: ReactNode
  error?: string
  children: (id: string) => ReactNode
}) {
  const id = useId()
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {help && <p className="field-help">{help}</p>}
      {children(id)}
      {hint && !error && <small className="muted">{hint}</small>}
      {error && (
        <small className="field-error" role="alert">
          {error}
        </small>
      )}
    </div>
  )
}

export const Input = (p: InputHTMLAttributes<HTMLInputElement>) => <input {...p} />
export const TextArea = (p: TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea rows={6} {...p} />
export const Select = (p: SelectHTMLAttributes<HTMLSelectElement>) => <select {...p} />
