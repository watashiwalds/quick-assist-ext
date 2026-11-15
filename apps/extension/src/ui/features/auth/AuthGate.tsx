import type { ReactNode } from 'react'
import { rpc } from '@/shared/messaging/client'
import type { SessionInfo } from '@/shared/messaging/protocol'
import { Button, ErrorState, Spinner } from '../../components'
import { useAction, useAsync, useBroadcast } from '../../lib/hooks'

/** Hiển thị màn đăng nhập nếu chưa có phiên; ngược lại render children với thông tin user. */
export function AuthGate({ children }: { children: (s: SessionInfo, reload: () => void) => ReactNode }) {
  const session = useAsync(() => rpc('auth/status'), [])
  const login = useAction()
  useBroadcast((e) => e.type === 'session/changed' && void session.reload())

  if (session.loading && !session.data) return <Spinner />
  if (session.error) return <ErrorState error={session.error} onRetry={session.reload} />
  const info = session.data
  if (!info?.signedIn) {
    const localMode = info?.authMode === 'local'
    return (
      <div className="state signin">
        <strong className="brand">QuickAssist</strong>
        <span>Lưu nhanh đoạn văn bản trên web, tóm tắt bằng AI và tìm lại theo ý nghĩa.</span>
        {localMode ? (
          <>
            {/* ADR-0016 §4.8: self-host một người — background tự dev-login khi server sẵn sàng;
                không có nút Google (server cũng không cấu hình OAuth). */}
            <Button busy={login.busy} onClick={() => void login.run(() => rpc('auth/status')).then((s) => s && session.setData(s))}>
              Kết nối lại server
            </Button>
            <small className="muted">
              Server đang ở chế độ tự host (không cần đăng nhập Google) — extension sẽ tự đăng nhập
              khi kết nối được. Hãy bảo vệ server bằng bind 127.0.0.1 hoặc proxy có xác thực.
            </small>
          </>
        ) : (
          <>
            <Button busy={login.busy} onClick={() => void login.run(() => rpc('auth/login')).then((s) => s && session.setData(s))}>
              Đăng nhập bằng Google
            </Button>
            {/* Chỉ bản build kiểm thử (npm run build:e2e): đăng nhập thử không cần Google. Vite thay
                import.meta.env.VITE_E2E lúc build → bản phát hành loại bỏ hẳn nhánh này (check:bundle chặn nếu lọt). */}
            {import.meta.env.VITE_E2E === 'true' && (
              <Button
                busy={login.busy}
                onClick={() =>
                  void login
                    .run(() => rpc('e2e/devLogin', { email: 'demo@quickassist.local' }))
                    .then((s) => s && session.setData(s))
                }
              >
                Đăng nhập thử (bản kiểm thử)
              </Button>
            )}
          </>
        )}
        {login.error && login.error.code !== 'OAUTH_CANCELLED' && <ErrorState error={login.error} />}
        <small className="muted">Chỉ lưu nội dung khi bạn chủ động ghi chú. Không thu thập lịch sử duyệt web.</small>
      </div>
    )
  }
  return <>{children(info, () => void session.reload())}</>
}
