import type { ReactNode } from 'react'
import { rpc } from '@/shared/messaging/client'
import type { SessionInfo } from '@/shared/messaging/protocol'
import { Button, ErrorState, Spinner } from '../../components'
import { useAsync, useBroadcast } from '../../lib/hooks'

/** Hiển thị màn đăng nhập nếu chưa có phiên; ngược lại render children với thông tin user. */
export function AuthGate({ children }: { children: (s: SessionInfo, reload: () => void) => ReactNode }) {
  const session = useAsync(() => rpc('auth/status'), [])
  useBroadcast((e) => e.type === 'session/changed' && void session.reload())

  if (session.loading && !session.data) return <Spinner />
  if (session.error) return <ErrorState error={session.error} onRetry={session.reload} />
  if (!session.data?.signedIn) {
    return (
      <div className="state">
        <strong>QuickAssist</strong>
        <span>Đăng nhập để lưu và tìm lại ghi chú của bạn.</span>
        <Button onClick={() => void rpc('auth/login').then(session.reload, session.reload)}>
          Đăng nhập bằng Google
        </Button>
      </div>
    )
  }
  return <>{children(session.data, () => void session.reload())}</>
}
