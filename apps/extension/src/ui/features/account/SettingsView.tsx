/**
 * Cài đặt (A08) — 3 mục: Chung, Tài khoản, Dịch vụ AI.
 *  - Chung: thư mục mặc định khi lưu nhanh (C04), tab “Tìm kiếm”, thông tin phiên bản.
 *  - Tài khoản: hồ sơ, hạn mức AI, đăng xuất, xoá tài khoản (xác nhận 2 bước).
 *  - Dịch vụ AI: cấu hình endpoint/BYOK (ProviderCard).
 * Rail dọc ở cửa sổ rộng, hàng tab ngang ở side panel (≤879px).
 */
import { useState } from 'react'
import { config } from '@/shared/config'
import { rpc } from '@/shared/messaging/client'
import type { Preferences, SessionInfo } from '@/shared/messaging/protocol'
import { resolveSplitChars, SPLIT_PRESETS } from '@/shared/notes/split'
import {
  Banner,
  Button,
  ConfirmDialog,
  ErrorState,
  Field,
  type IconName,
  Icon,
  Modal,
  ProgressBar,
  Select,
  Spinner,
  useToast,
} from '../../components'
import { useAction, useAsync, useBroadcast } from '../../lib/hooks'
import { ProviderCard } from './ProviderCard'

const fmt = (n: number) => n.toLocaleString('vi-VN')

export type SettingsSection = 'general' | 'account' | 'ai'

type Section = SettingsSection

const SECTIONS: Array<{ key: Section; label: string; icon: IconName }> = [
  { key: 'general', label: 'Chung', icon: 'sliders' },
  { key: 'account', label: 'Tài khoản', icon: 'user' },
  { key: 'ai', label: 'Dịch vụ AI', icon: 'sparkles' },
]

/** Phiên bản extension (manifest); rỗng khi môi trường test không có getManifest. */
function appVersion(): string {
  try {
    return chrome.runtime.getManifest().version
  } catch {
    return ''
  }
}

export function SettingsView({
  session,
  onPrefsChanged,
  demo = config.e2e,
  initialSection = 'general',
}: {
  session: SessionInfo
  onPrefsChanged?: (p: Preferences) => void
  /** Bản demo (build:e2e) hiện nút tạo lại hạn mức. */
  demo?: boolean
  /** Mở thẳng một mục (vd. “Xem hạn mức” → Tài khoản). */
  initialSection?: Section
}) {
  const quota = useAsync(() => rpc('quota/get'), [])
  const prefs = useAsync(() => rpc('prefs/get'), [])
  const folders = useAsync(() => rpc('folders/list'), [])
  const [section, setSection] = useState<Section>(initialSection)
  const [aboutOpen, setAboutOpen] = useState(false)
  const [step, setStep] = useState<0 | 1 | 2>(0)
  const logoutAct = useAction()
  const delAct = useAction()
  const resetAct = useAction()
  const toast = useToast()
  useBroadcast((e) => e.type === 'folders/changed' && void folders.reload())
  const u = session.user
  const localMode = session.authMode === 'local'
  // BYOK: user tự trả tiền AI qua key riêng → được đặt lại số liệu (ADR-0016 D6).
  const byok = quota.data?.billing_mode === 'byok'
  // DEV_UNLIMITED: quota vẫn đếm nhưng backend không chặn; UI không được báo "hết hạn mức".
  const unlimited = quota.data?.limit_enforced === false
  const usedTotal = quota.data ? quota.data.used_tokens + quota.data.reserved_tokens : 0
  const overLimit = !!quota.data && usedTotal > quota.data.limit_tokens
  const version = appVersion()
  const displayName = u?.display_name ?? (localMode ? 'Tự host' : 'Tài khoản Google')
  const active = (key: Section) => (section === key ? ' is-active' : '')

  return (
    <div className="settings">
      <aside className="settings-rail">
        <div className="settings-rail-head">
          <h2>Cài đặt</h2>
          <p>Tuỳ chỉnh QuickAssist trên trình duyệt này.</p>
        </div>

        <nav className="settings-nav" aria-label="Mục cài đặt">
          {SECTIONS.map((s) => (
            <button
              key={s.key}
              type="button"
              className="settings-nav-item"
              aria-current={section === s.key ? 'page' : undefined}
              onClick={() => setSection(s.key)}
            >
              <Icon name={s.icon} size={16} />
              <span>{s.label}</span>
              <Icon name="chevron-right" size={14} className="settings-nav-chevron" />
            </button>
          ))}
        </nav>

        <div className="settings-rail-foot">
          <span className="settings-rail-avatar" aria-hidden>
            {u?.avatar_url ? <img src={u.avatar_url} alt="" referrerPolicy="no-referrer" /> : <Icon name="user" size={15} />}
          </span>
          <span className="settings-rail-user">
            <strong>{displayName}</strong>
            <span>{u?.email}</span>
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="icon-only"
            aria-label="Về QuickAssist"
            title="Về QuickAssist"
            onClick={() => setAboutOpen(true)}
          >
            <Icon name="info" size={15} />
          </Button>
        </div>
      </aside>

      <div className="settings-main">
        {/* ---------- Chung ---------- */}
        <section className={`settings-panel${active('general')}`} aria-labelledby="settings-general-title">
          <div className="settings-head">
            <h2 id="settings-general-title">Chung</h2>
            <p className="settings-lede">
              Tuỳ chọn áp dụng cho toàn bộ QuickAssist trên trình duyệt này. Thay đổi được lưu ngay.
            </p>
          </div>

          <div className="settings-body">
            <section className="card settings-card">
              <div className="settings-card-head">
                <h3>Lưu nhanh</h3>
                <p>
                  Áp dụng cho <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>N</kbd> và mục “Ghi chú văn bản này” trong
                  menu chuột phải.
                </p>
              </div>
              <Field
                label="Thư mục mặc định"
                hint="Muốn chọn thư mục khác cho từng ghi chú: chuột phải → “Ghi chú vào thư mục”."
              >
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
            </section>

            <section className="card settings-card">
              <div className="settings-card-head">
                <h3>Thanh tab</h3>
                <p>Tab “Tìm kiếm” đã gộp vào thanh tìm của Thư viện.</p>
              </div>
              <label className="settings-check" htmlFor="qa-show-search-tab">
                <input
                  id="qa-show-search-tab"
                  type="checkbox"
                  checked={!!prefs.data?.showSearchTab}
                  disabled={!prefs.data}
                  onChange={(e) =>
                    void rpc('prefs/set', { showSearchTab: e.target.checked })
                      .then((p) => {
                        prefs.setData(p)
                        onPrefsChanged?.(p)
                        toast(e.target.checked ? 'Đã hiện lại tab Tìm kiếm' : 'Đã ẩn tab Tìm kiếm')
                      })
                      .catch(() => toast('Không lưu được tuỳ chọn', 'error'))
                  }
                />
                <span>Hiện tab “Tìm kiếm” trên thanh tab</span>
              </label>
              <p className="settings-hint">
                Gõ trong Thư viện để lọc nhanh; nhấn <kbd>Enter</kbd> để tìm sâu bằng AI. Bật lại nếu bạn vẫn
                muốn tab riêng.
              </p>
            </section>

            <section className="card settings-card">
              <div className="settings-card-head">
                <h3>Tài liệu dài</h3>
                <p>
                  Nội dung dài hơn ngưỡng được chia thành nhiều phần ≤ {config.maxNoteChars.toLocaleString('vi-VN')}{' '}
                  ký tự và lưu thành một tài liệu duy nhất.
                </p>
              </div>
              <Field
                label="Ngưỡng chia mỗi phần"
                hint="Ngưỡng thấp hơn giúp mỗi phần dễ đọc hơn nhưng tạo nhiều phần hơn. Không thể vượt giới hạn của máy chủ."
              >
                {(id) => (
                  <Select
                    id={id}
                    value={String(resolveSplitChars(prefs.data?.splitChars))}
                    disabled={!prefs.data}
                    onChange={(e) =>
                      void rpc('prefs/set', { splitChars: Number(e.target.value) })
                        .then((p) => {
                          prefs.setData(p)
                          onPrefsChanged?.(p)
                          toast('Đã lưu ngưỡng chia tài liệu')
                        })
                        .catch(() => toast('Không lưu được tuỳ chọn', 'error'))
                    }
                  >
                    {SPLIT_PRESETS.map((n) => (
                      <option key={n} value={n}>
                        {n.toLocaleString('vi-VN')} ký tự
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </section>

            <section className="card settings-card">
              <div className="settings-card-head">
                <h3>Về QuickAssist</h3>
                <p>{version ? `Phiên bản ${version}` : 'Trợ lý học tập cho ghi chú và hỏi AI.'}</p>
              </div>
              <div className="settings-actions">
                <Button variant="ghost" size="sm" onClick={() => setAboutOpen(true)}>
                  Xem thông tin
                </Button>
              </div>
            </section>
          </div>
        </section>

        {/* ---------- Tài khoản ---------- */}
        <section className={`settings-panel${active('account')}`} aria-labelledby="settings-account-title">
          <div className="settings-head">
            <h2 id="settings-account-title">Tài khoản</h2>
            <p className="settings-lede">Hồ sơ, hạn mức AI và các thao tác không thể hoàn tác.</p>
          </div>

          <div className="settings-body">
            <section className="card settings-card settings-profile">
              <span className="settings-avatar" aria-hidden>
                {u?.avatar_url ? (
                  <img src={u.avatar_url} alt="" referrerPolicy="no-referrer" />
                ) : (
                  <Icon name="user" size={20} />
                )}
              </span>
              <div className="grow">
                <strong>{displayName}</strong>
                <div className="muted">{u?.email}</div>
                {u?.created_at && (
                  <small className="muted">
                    Tham gia {new Date(u.created_at).toLocaleDateString('vi-VN')}
                  </small>
                )}
              </div>
              <span className="badge">{localMode ? 'Tự host' : 'Google'}</span>
            </section>

            <section className="card settings-card">
              <div className="settings-quota-head">
                <div className="settings-card-head">
                  <h3>Hạn mức AI</h3>
                  <p>Dùng cho Hỏi AI, tìm kiếm ngữ nghĩa và tóm tắt.</p>
                </div>
                <div className="settings-actions">
                  {(demo || byok) && (
                    <Button
                      variant="soft"
                      size="sm"
                      busy={resetAct.busy}
                      onClick={() =>
                        void resetAct.run(() => rpc('quota/reset')).then((q) => {
                          if (!q) return
                          quota.setData(q)
                          toast(byok ? 'Đã đặt lại số liệu' : 'Đã tạo lại hạn mức AI')
                        })
                      }
                    >
                      {byok ? 'Đặt lại số liệu' : 'Tạo lại hạn mức'}
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => void quota.reload()}>
                    <Icon name="sync" size={14} />
                    Làm mới
                  </Button>
                </div>
              </div>

              {resetAct.error && <ErrorState error={resetAct.error} />}
              {quota.loading && !quota.data && <Spinner />}
              {quota.error && <ErrorState error={quota.error} onRetry={quota.reload} />}
              {quota.data && (
                <>
                  <ProgressBar
                    value={usedTotal}
                    max={unlimited ? Math.max(quota.data.limit_tokens, usedTotal) : quota.data.limit_tokens}
                    label={
                      unlimited
                        ? 'Đã dùng (dev không giới hạn)'
                        : byok
                          ? 'Đã dùng (key của bạn)'
                          : 'Đã dùng hạn mức AI'
                    }
                  />
                  {unlimited ? (
                    <div className="settings-quota-meta">
                      <span>
                        Đã dùng <strong>{fmt(quota.data.used_tokens)}</strong> token · ngưỡng{' '}
                        {fmt(quota.data.limit_tokens)} (không chặn)
                      </span>
                    </div>
                  ) : (
                    <div className="settings-quota-meta">
                      <span>
                        {byok ? 'Đã dùng (key của bạn)' : 'Đã dùng'} <strong>{fmt(quota.data.used_tokens)}</strong> /{' '}
                        {fmt(quota.data.limit_tokens)} token
                      </span>
                      <span>
                        Còn lại <strong>{fmt(quota.data.remaining_tokens)}</strong>
                      </span>
                    </div>
                  )}
                  {unlimited ? (
                    <p className="settings-hint">
                      Dev mode: quota vẫn được ghi nhận nhưng không giới hạn; rate limit theo user cũng đã tắt.
                    </p>
                  ) : byok ? (
                    <p className="settings-hint">
                      Bạn đang dùng key AI riêng (BYOK): lời gọi AI vẫn tính vào hạn mức của server. Bạn có thể
                      bấm “Đặt lại số liệu” bất cứ lúc nào để tiếp tục.
                    </p>
                  ) : (
                    <p className="settings-hint">
                      Hạn mức được đặt lại bởi quản trị viên hoặc khi bạn dùng khoá AI riêng.
                    </p>
                  )}
                  {unlimited && (
                    <Banner tone={overLimit ? 'warn' : 'info'}>
                      Dev mode: vẫn đếm token nhưng không khoá tính năng AI.
                      {overLimit ? ` Đã vượt ngưỡng ${fmt(quota.data.limit_tokens)} token.` : ''}
                    </Banner>
                  )}
                  {!unlimited && quota.data.remaining_tokens === 0 && (
                    <Banner tone="warn">
                      Đã hết hạn mức: ghi chú mới vẫn được lưu nhưng chưa tìm kiếm ngữ nghĩa/tóm tắt được.
                      {byok ? ' Bấm “Đặt lại số liệu” để tiếp tục.' : ''}
                    </Banner>
                  )}
                </>
              )}
            </section>

            {/* Local mode (ADR-0016 §4.8): ẩn Đăng xuất — bấm sẽ bị tự đăng nhập lại ngay. */}
            {!localMode && (
              <section className="card settings-card">
                <div className="settings-card-head">
                  <h3>Phiên đăng nhập</h3>
                  <p>Đăng xuất sẽ xoá bộ nhớ đệm ghi chú trên máy này.</p>
                </div>
                <div className="settings-actions">
                  <Button
                    variant="ghost"
                    busy={logoutAct.busy}
                    onClick={() => void logoutAct.run(() => rpc('auth/logout'))}
                  >
                    <Icon name="logout" size={15} />
                    Đăng xuất
                  </Button>
                </div>
                {logoutAct.error && <ErrorState error={logoutAct.error} />}
              </section>
            )}

            <section className="card settings-card danger-zone">
              <div className="settings-card-head">
                <h3>Xoá tài khoản</h3>
                <p>
                  Xoá vĩnh viễn tài khoản cùng toàn bộ ghi chú, thư mục, chỉ mục tìm kiếm và lịch sử hạn mức.
                  Không thể khôi phục.
                </p>
              </div>
              <div className="settings-actions">
                <Button variant="danger" onClick={() => setStep(1)}>
                  <Icon name="trash" size={15} />
                  Xoá tài khoản…
                </Button>
              </div>
            </section>
          </div>
        </section>

        {/* ---------- Dịch vụ AI ---------- */}
        <section className={`settings-panel${active('ai')}`} aria-labelledby="settings-ai-title">
          <div className="settings-head">
            <h2 id="settings-ai-title">Cấu hình Endpoint</h2>
            <p className="settings-lede">
              Chọn cách QuickAssist gọi AI. Endpoint riêng vẫn được gọi qua server QuickAssist để bảo vệ khoá API
              và tính hạn mức; khoá không được lưu trong trình duyệt.
            </p>
          </div>

          <ProviderCard onChanged={quota.data ? () => void quota.reload() : undefined} />
        </section>
      </div>

      <Modal
        open={aboutOpen}
        title="Về QuickAssist"
        onClose={() => setAboutOpen(false)}
        footer={<Button variant="ghost" onClick={() => setAboutOpen(false)}>Đóng</Button>}
      >
        <div className="settings-about-brand">
          <span className="brand-mark" aria-hidden>
            <Icon name="note" size={16} />
          </span>
          <div>
            <strong>QuickAssist</strong>
            {version && <div className="muted">Phiên bản {version}</div>}
          </div>
        </div>
        <p className="modal-lede">
          QuickAssist giúp bạn lưu ghi chú từ trang web, tìm kiếm ngữ nghĩa và hỏi AI trên chính ghi chú của mình.
        </p>
        <dl className="settings-about-list">
          <div>
            <dt>Ghi chú</dt>
            <dd>Đồng bộ với server của bạn.</dd>
          </div>
          <div>
            <dt>Lịch sử hội thoại</dt>
            <dd>Chỉ lưu trên trình duyệt này.</dd>
          </div>
          <div>
            <dt>Khoá API</dt>
            <dd>Mã hoá trên server, không lưu trong trình duyệt.</dd>
          </div>
        </dl>
      </Modal>

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
        message={
          <>
            <p>Tài khoản {u?.email ?? ''} sẽ bị xoá ngay lập tức.</p>
            {delAct.error && <ErrorState error={delAct.error} />}
          </>
        }
        confirmLabel="Xoá vĩnh viễn"
        confirmText="XOÁ"
        danger
        busy={delAct.busy}
        onCancel={() => setStep(0)}
        onConfirm={() => void delAct.run(() => rpc('account/delete')).then(() => setStep(0))}
      />
    </div>
  )
}
