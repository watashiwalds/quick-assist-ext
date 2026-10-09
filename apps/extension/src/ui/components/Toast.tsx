/** Thông báo ngắn trong giao diện (không phải toast trên trang web). Tự ẩn sau 4 giây. */
import { createContext, type ReactNode, useCallback, useContext, useState } from 'react'

type Tone = 'ok' | 'error' | 'info'
interface ToastMsg {
  id: number
  text: string
  tone: Tone
}
const Ctx = createContext<(text: string, tone?: Tone) => void>(() => undefined)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastMsg[]>([])
  const push = useCallback((text: string, tone: Tone = 'ok') => {
    const id = Date.now() + Math.random()
    setItems((xs) => [...xs.slice(-2), { id, text, tone }])
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 4000)
  }, [])
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`} role={t.tone === 'error' ? 'alert' : 'status'}>
            {t.text}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  )
}

export const useToast = () => useContext(Ctx)
