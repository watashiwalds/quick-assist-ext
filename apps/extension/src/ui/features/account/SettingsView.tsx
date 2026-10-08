/**
 * Cài đặt (A08): thông tin tài khoản, hạn mức AI còn lại, thư mục mặc định khi lưu nhanh (C04),
 * đăng xuất, xoá tài khoản (xác nhận 2 bước: hộp thoại + gõ "XOÁ") — xoá cả dữ liệu trên máy.
 */
import { useState } from 'react'
import { rpc } from '@/shared/messaging/client'
import type { SessionInfo } from '@/shared/messaging/protocol'
import { Banner, Button, ConfirmDialog, ErrorState, Field, ProgressBar, Select, Spinner, useToast } from '../../components'
import { formatDate, useAction, useAsync, useBroadcast } from '../../lib/hooks'

const fmt = (n: number) => n.toLocaleString('vi-VN')

export function SettingsView({ session }: { session: SessionInfo }) {
  const quota = useAsync(() => rpc('quota/get'), [])
  const prefs = useAsync(() => rpc('prefs/get'), [])
  const folders = useAsync(() => rpc('folders/list'), [])
  const [step, setStep] = useState<0 | 1 | 2>(0)
  const act = useAction()
  const toast = useToast()
  useBroadcast((e) => e.type === 'folders/changed' && void folders.reload())
  const u = session.user

  return (
    <section className="stack" aria-label="Cài đặt">
      <div className="card row">
        {u?.avatar_url && <img className="avatar" src={u.avatar_url} alt="" referrerPolicy="no-referrer" />}
        <div className="grow">
          <strong>{u?.display_name ?? 'Tài khoản Google'}</strong>
          <div className="muted">{u?.email}</div>
          {u?.created_at && <small className="muted">Tham gia {formatDate(u.created_at)}</small>}
        </div>
      </div>

      <div className="card stack">
        <div className="row spread">
          <strong>Hạn mức AI</strong>
          <Button variant="link" size="sm" onClick={() => void quota.reload()}>
            Làm mới
          </Button>
        </div>
        {quota.loading && !quota.data && <Spinner />}
        {quota.error && <ErrorState error={quota.error} onRetry={quota.reload} />}
        {quota.data && (
          <>
            <ProgressBar value={quota.data.used_tokens + quota.data.reserved_tokens} max={quota.data.limit_tokens} label="Đã dùng hạn mức AI" />
            <div className="muted">
              Đã dùng {fmt(quota.data.used_tokens)} / {fmt(quota.data.limit_tokens)} token · còn lại <strong>{fmt(quota.data.remaining_tokens)}</strong>
            </div>
            {quota.data.remaining_tokens === 0 && (
              <Banner tone="warn">Đã hết hạn mức: ghi chú mới vẫn được lưu nhưng chưa tìm kiếm ngữ nghĩa/tóm tắt được.</Banner>
            )}
          </>
        )}
      </div>

      <div className="card stack">
        <Field label="Thư mục mặc định khi lưu nhanh (Alt+Shift+N, “Ghi chú văn bản này”)">
          {(id) => (
            <Select
              id={id}
              value={prefs.data?.defaultFolderId ?? ''}
              disabled={!prefs.data}
              onChange={(e) =>
                void rpc('prefs/set', { defaultFolderId: e.target.value || null })
                  .then((p) => {
                    prefs.setData(p)
                    toast('Đã lưu thư mục mặc định')
                  })
                  .catch(() => toast('Không lưu được tuỳ chọn', 'error'))
              }
            >
              <option value="">Inbox</option>
              {folders.data?.filter((f) => !f.is_default).map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <small className="muted">Muốn chọn thư mục khác cho từng ghi chú: chuột phải → “Ghi chú vào thư mục”.</small>
      </div>

      <div className="card stack">
        <Button variant="ghost" busy={act.busy && step === 0} onClick={() => void act.run(() => rpc('auth/logout'))}>
          Đăng xuất
        </Button>
        <small className="muted">Đăng xuất xoá bộ nhớ đệm ghi chú trên máy này.</small>
      </div>

      <div className="card stack danger-zone">
        <strong>Xoá tài khoản</strong>
        <span className="muted">Xoá vĩnh viễn tài khoản cùng toàn bộ ghi chú, thư mục, chỉ mục tìm kiếm và lịch sử hạn mức. Không thể khôi phục.</span>
        <Button variant="danger" onClick={() => setStep(1)}>
          Xoá tài khoản…
        </Button>
        {act.error && <ErrorState error={act.error} />}
      </div>

      <ConfirmDialog
        open={step === 1}
        title="Xoá tài khoản? (bước 1/2)"
        message={
          <ul>
            <li>Mọi ghi chú và thư mục sẽ bị xoá trên máy chủ.</li>
            <li>Ghi chú đang chờ gửi trên máy này cũng bị xoá.</li>
            <li>Bạn có thể đăng nhập lại sau, nhưng sẽ bắt đầu với thư viện trống.</li>
          </ul>
        }
        confirmLabel="Tiếp tục"
        danger
        onCancel={() => setStep(0)}
        onConfirm={() => setStep(2)}
      />
      <ConfirmDialog
        open={step === 2}
        title="Xác nhận xoá tài khoản (bước 2/2)"
        message={`Tài khoản ${u?.email ?? ''} sẽ bị xoá ngay lập tức.`}
        confirmLabel="Xoá vĩnh viễn"
        confirmText="XOÁ"
        danger
        busy={act.busy}
        onCancel={() => setStep(0)}
        onConfirm={() => void act.run(() => rpc('account/delete')).then(() => setStep(0))}
      />
    </section>
  )
}
