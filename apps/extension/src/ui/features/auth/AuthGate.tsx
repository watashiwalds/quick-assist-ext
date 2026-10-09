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
  if (!session.data?.signedIn) {
    return (
      <div className="state signin">
        <strong className="brand">QuickAssist</strong>
        <span>Lưu nhanh đoạn văn bản trên web, tóm tắt bằng AI và tìm lại theo ý nghĩa.</span>
        <Button busy={login.busy} onClick={() => void login.run(() => rpc('auth/login')).then((s) => s && session.setData(s))}>
          Đăng nhập bằng Google
        </Button>
        {login.error && login.error.code !== 'OAUTH_CANCELLED' && <ErrorState error={login.error} />}
        <small className="muted">Chỉ lưu nội dung khi bạn chủ động ghi chú. Không thu thập lịch sử duyệt web.</small>
      </div>
    )
  }
  return <>{children(session.data, () => void session.reload())}</>
}
