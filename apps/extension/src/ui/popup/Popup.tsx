/** Popup nhỏ trên thanh công cụ: trạng thái đăng nhập + mở side panel. */
import { Button } from '../components'
import { AuthGate } from '../features/auth/AuthGate'

async function openSidePanel() {
  const win = await chrome.windows.getCurrent()
  if (win.id !== undefined) await chrome.sidePanel.open({ windowId: win.id })
  window.close()
}

export function Popup() {
  return (
    <div style={{ width: 300, padding: 12 }}>
      <AuthGate>
        {(s) => (
          <div className="state">
            <strong>Xin chào {s.user?.display_name ?? s.user?.email}</strong>
            <span className="muted">Bôi đen văn bản → chuột phải → “Ghi chú văn bản này” (Ctrl+Alt+N)</span>
            <Button onClick={() => void openSidePanel()}>Mở thư viện ghi chú</Button>
          </div>
        )}
      </AuthGate>
    </div>
  )
}
