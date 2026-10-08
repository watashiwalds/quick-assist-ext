/** Popup nhỏ trên thanh công cụ: trạng thái đăng nhập, hạn mức, mở side panel. */
import { rpc } from '@/shared/messaging/client'
import { Button, ProgressBar, ToastProvider } from '../components'
import { AuthGate } from '../features/auth/AuthGate'
import { useAsync } from '../lib/hooks'

async function openSidePanel() {
  const win = await chrome.windows.getCurrent()
  if (win.id !== undefined) await chrome.sidePanel.open({ windowId: win.id })
  window.close()
}

function QuotaLine() {
  const q = useAsync(() => rpc('quota/get'), [])
  if (!q.data) return null
  return (
    <div className="stack quota-mini">
      <ProgressBar value={q.data.used_tokens} max={q.data.limit_tokens} label="Hạn mức AI đã dùng" />
      <small className="muted">Còn {q.data.remaining_tokens.toLocaleString('vi-VN')} token AI</small>
    </div>
  )
}

export function Popup() {
  return (
    <ToastProvider>
      <div className="popup">
        <AuthGate>
          {(s) => (
            <div className="stack">
              <strong>Xin chào {s.user?.display_name ?? s.user?.email}</strong>
              <span className="muted">Bôi đen văn bản → chuột phải → “Ghi chú văn bản này” hoặc nhấn Alt+Shift+N.</span>
              <QuotaLine />
              <Button onClick={() => void openSidePanel()}>Mở thư viện ghi chú</Button>
            </div>
          )}
        </AuthGate>
      </div>
    </ToastProvider>
  )
}
