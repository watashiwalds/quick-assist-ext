/** Tabs theo mẫu WAI-ARIA: ←/→/Home/End di chuyển, roving tabindex (A05 — điều hướng bàn phím). */
import { type KeyboardEvent, useRef } from 'react'

export interface TabItem<K extends string> {
  key: K
  label: string
  badge?: number
}

export function Tabs<K extends string>({ items, value, onChange }: { items: TabItem<K>[]; value: K; onChange: (k: K) => void }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const onKey = (e: KeyboardEvent, i: number) => {
    const n = items.length
    const to = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i - 1 + n) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1
    if (to < 0) return
    e.preventDefault()
    refs.current[to]?.focus()
    onChange(items[to]!.key)
  }
  return (
    <div className="tabs" role="tablist" aria-label="Chức năng">
      {items.map((t, i) => (
        <button
          key={t.key}
          ref={(el) => {
            refs.current[i] = el
          }}
          type="button"
          role="tab"
          id={`tab-${t.key}`}
          aria-controls={`panel-${t.key}`}
          aria-selected={t.key === value}
          tabIndex={t.key === value ? 0 : -1}
          className="tab"
          onClick={() => onChange(t.key)}
          onKeyDown={(e) => onKey(e, i)}
        >
          {t.label}
          {!!t.badge && <span className="tab-badge" aria-label={`${t.badge} mục`}>{t.badge}</span>}
        </button>
      ))}
    </div>
  )
}
