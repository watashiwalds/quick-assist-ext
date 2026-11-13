/**
 * Hỏi đáp AI trên ghi chú (X02, SDS §5.1.6) — giao diện redesign theo demo
 * `upgrade-plan/redesign/aichat/demo`: split-view "rail phiên + hội thoại" ở cửa sổ rộng,
 * thu thành hội thoại toàn chiều rộng + drawer ở side panel hẹp (≤880px).
 *
 * Ngôn ngữ thị giác trùng Thư viện / Tìm trong trang: chỉ dùng token A05, radius 8px, system font.
 * Tái dùng component sẵn có (Button, Select, TextArea, Modal, ConfirmDialog, ProgressBar, Icon).
 *
 * Tầng dữ liệu vẫn ở `useChatSessions` (không đổi luồng hỏi/đáp): rail chỉ gọi `switchSession`,
 * `newSession`, `renameSession`, `deleteSession`, `clearSessions`; dung lượng lấy qua RPC
 * `chatSessions/usage` (background sở hữu key — UI không đọc storage trực tiếp).
 */
import { type FormEvent, type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from 'react'
import type { ChatSource } from '@/shared/api/types'
import { type ChatMessageItem, type ChatSession } from '@/shared/chat'
import { type SerializedError, userMessage } from '@/shared/errors'
import { rpc } from '@/shared/messaging/client'
import { Button, ConfirmDialog, Icon, Modal, ProgressBar, Select, TextArea, useToast } from '../../components'
import { useAsync } from '../../lib/hooks'
import type { ChatState } from './useChat'

const EXAMPLES = ['Tóm tắt những gì mình đã lưu tuần này', 'Ghi chú nào nói về cách nấu phở?', 'So sánh các ý chính trong ghi chú về Kubernetes']

/** Mặc định ổn định (không tạo mảng mới mỗi render — `useAsync` sẽ reload liên tục nếu đổi identity). */
const NO_SESSIONS: ChatSession[] = []

interface ChatViewProps {
  chat: ChatState
  /** Đã đọc xong lịch sử chưa — composer/rail tạm khoá để tránh nháy "Trống" rồi mới có phiên. */
  ready?: boolean
  sessions?: ChatSession[]
  activeId?: string | null
  onSwitchSession?: (id: string) => void
  onNewSession?: () => void
  onRenameSession?: (id: string, title: string) => void
  onDeleteSession?: (id: string) => void
  onClearSessions?: () => void
  onOpenNote: (noteId: string) => void
  onGoSettings: () => void
}

/** Ngày cập nhật phiên, dạng ngắn 13/11/26 như demo. */
function formatDate(ts: number): string {
  return new Date(ts).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

/** Số lượt hỏi–đáp = số câu hỏi của người dùng (cap 20 cặp/phiên). */
function turnCount(session: ChatSession): number {
  return session.messages.filter((m) => m.role === 'user').length
}

/** MB với dấu phẩy thập phân kiểu Việt Nam (4,9 MB). */
function formatMb(bytes: number): string {
  const mb = Math.round((bytes / (1024 * 1024)) * 10) / 10
  return `${mb.toLocaleString('vi-VN', { maximumFractionDigits: 1 })} MB`
}

/** Đọc kết quả RPC dung lượng; bỏ qua dữ liệu lạ (background cũ chưa có handler). */
function readUsage(data: unknown): { bytes: number; quota: number } | undefined {
  if (!data || typeof data !== 'object') return undefined
  const { bytes, quota } = data as { bytes?: unknown; quota?: unknown }
  if (typeof bytes !== 'number' || typeof quota !== 'number' || quota <= 0) return undefined
  return { bytes, quota }
}

/** Câu hỏi của người dùng ngay trước câu trả lời `id` — dùng cho "Hỏi lại". */
function previousQuestion(messages: ChatMessageItem[], id: string): string {
  const i = messages.findIndex((m) => m.id === id)
  for (let j = i - 1; j >= 0; j--) {
    const m = messages[j]
    if (m?.role === 'user') return m.text
  }
  return ''
}

type ConfirmTarget = { kind: 'one'; session: ChatSession } | { kind: 'all' }

export function ChatView({
  chat,
  ready = true,
  sessions = NO_SESSIONS,
  activeId = null,
  onSwitchSession,
  onNewSession,
  onRenameSession,
  onDeleteSession,
  onClearSessions,
  onOpenNote,
  onGoSettings,
}: ChatViewProps) {
  const [query, setQuery] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [managing, setManaging] = useState(false)
  const [confirm, setConfirm] = useState<ConfirmTarget | null>(null)
  const toast = useToast()

  const usage = useAsync(() => rpc('chatSessions/usage'), [sessions])
  const usageInfo = readUsage(usage.data)
  const active = activeId ? (sessions.find((s) => s.id === activeId) ?? null) : null

  // Esc đóng drawer phiên (modal có bẫy focus/Esc riêng).
  useEffect(() => {
    if (!drawerOpen) return
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') setDrawerOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawerOpen])

  function copyAnswer(text: string) {
    if (!navigator.clipboard?.writeText) {
      toast('Trình duyệt không cho phép sao chép tự động.', 'error')
      return
    }
    void navigator.clipboard.writeText(text).then(
      () => toast('Đã sao chép câu trả lời.'),
      () => toast('Không sao chép được câu trả lời.', 'error'),
    )
  }

  function switchTo(id: string) {
    setDrawerOpen(false)
    onSwitchSession?.(id)
  }

  function startNew() {
    setDrawerOpen(false)
    onNewSession?.()
  }

  function runConfirm() {
    if (!confirm) return
    if (confirm.kind === 'all') onClearSessions?.()
    else onDeleteSession?.(confirm.session.id)
    setConfirm(null)
    setManaging(false)
  }

  const totalTurns = sessions.reduce((n, s) => n + turnCount(s), 0)

  return (
    <section className={`aichat${drawerOpen ? ' drawer-open' : ''}`} aria-label="Hỏi đáp với ghi chú">
      <ChatSessionRail
        sessions={sessions}
        activeId={activeId}
        ready={ready}
        streaming={chat.streaming}
        query={query}
        onQuery={setQuery}
        onSwitch={switchTo}
        onNew={startNew}
        onManage={() => setManaging(true)}
        usage={usageInfo}
        onCloseDrawer={() => setDrawerOpen(false)}
      />
      <button type="button" className="drawer-scrim" aria-label="Đóng danh sách phiên" onClick={() => setDrawerOpen(false)} />

      <ChatConversation
        chat={chat}
        ready={ready}
        active={active}
        onToggleDrawer={() => setDrawerOpen(true)}
        onRename={(title) => {
          if (active) onRenameSession?.(active.id, title)
        }}
        onDelete={() => {
          if (active) setConfirm({ kind: 'one', session: active })
        }}
        onOpenNote={onOpenNote}
        onGoSettings={onGoSettings}
        onCopy={copyAnswer}
      />

      <Modal
        open={managing}
        title="Quản lý phiên"
        onClose={() => setManaging(false)}
        footer={
          <>
            <Button
              variant="danger-ghost"
              size="sm"
              onClick={() => {
                setManaging(false)
                setConfirm({ kind: 'all' })
              }}
              disabled={!sessions.length}
            >
              <Icon name="trash" size={14} />
              Xoá tất cả
            </Button>
            <span className="grow" />
            <Button variant="ghost" onClick={() => setManaging(false)}>
              Đóng
            </Button>
          </>
        }
      >
        <div className="manage-sheet">
          <p className="manage-lede">
            Lịch sử hội thoại chỉ nằm trên trình duyệt này và sẽ bị xoá khi bạn đăng xuất. Xoá phiên không ảnh hưởng đến ghi
            chú của bạn.
          </p>
          {usageInfo && (
            <div className="storage storage-inline">
              <div className="storage-row">
                <span>
                  Đã dùng <strong>{formatMb(usageInfo.bytes)}</strong>
                </span>
                <span className="storage-size">trên {formatMb(usageInfo.quota)}</span>
              </div>
              <ProgressBar value={usageInfo.bytes} max={usageInfo.quota} label="Đã dùng dung lượng lịch sử hội thoại" />
            </div>
          )}
          {sessions.length > 0 ? (
            <ul className="manage-list">
              {sessions.map((s) => (
                <li key={s.id} className="manage-item">
                  <div className="manage-copy">
                    <p className="manage-title">{s.title}</p>
                    <p className="manage-meta">
                      {formatDate(s.updatedAt)} · {turnCount(s)} lượt
                      {s.id === activeId && <span className="chip-open">Đang mở</span>}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="icon-only"
                    aria-label={`Xoá phiên ${s.title}`}
                    title="Xoá phiên"
                    onClick={() => {
                      setManaging(false)
                      setConfirm({ kind: 'one', session: s })
                    }}
                  >
                    <Icon name="trash" size={15} />
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Chưa có phiên nào được lưu.</p>
          )}
          <p className="modal-safe">
            <Icon name="lock" size={12} />
            Ghi chú của bạn không bị xoá khi xoá phiên hội thoại.
          </p>
        </div>
      </Modal>

      <ConfirmDialog
        open={confirm !== null}
        title={confirm?.kind === 'all' ? 'Xoá toàn bộ lịch sử hội thoại?' : 'Xoá cuộc trò chuyện này?'}
        message={
          confirm?.kind === 'all'
            ? `Toàn bộ ${sessions.length} phiên (${totalTurns} lượt hỏi–đáp) sẽ bị xoá khỏi trình duyệt này. Không thể hoàn tác; ghi chú của bạn không bị ảnh hưởng.`
            : confirm
              ? `Phiên “${confirm.session.title}” và ${turnCount(confirm.session)} lượt hỏi–đáp sẽ bị xoá khỏi trình duyệt. Ghi chú của bạn không bị ảnh hưởng.`
              : null
        }
        confirmLabel={confirm?.kind === 'all' ? 'Xoá tất cả' : 'Xoá phiên'}
        danger
        {...(confirm?.kind === 'all' ? { confirmText: 'XOÁ' } : {})}
        onConfirm={runConfirm}
        onCancel={() => setConfirm(null)}
      />
    </section>
  )
}

/** Rail phiên: tiêu đề + Mới, tìm theo tiêu đề, danh sách phiên, footer dung lượng + Quản lý. */
function ChatSessionRail({
  sessions,
  activeId,
  ready,
  streaming,
  query,
  onQuery,
  onSwitch,
  onNew,
  onManage,
  usage,
  onCloseDrawer,
}: {
  sessions: ChatSession[]
  activeId: string | null
  ready: boolean
  streaming: boolean
  query: string
  onQuery: (q: string) => void
  onSwitch: (id: string) => void
  onNew: () => void
  onManage: () => void
  usage: { bytes: number; quota: number } | undefined
  onCloseDrawer: () => void
}) {
  const q = query.trim().toLowerCase()
  const filtered = q ? sessions.filter((s) => s.title.toLowerCase().includes(q)) : sessions

  return (
    <aside className="session-pane" aria-labelledby="chat-sessions-title">
      <div className="session-head">
        <div className="session-title-row">
          <h2 id="chat-sessions-title">Hội thoại</h2>
          <span className="grow" />
          <Button variant="ghost" size="sm" className="icon-only drawer-close" aria-label="Đóng" title="Đóng danh sách phiên" onClick={onCloseDrawer}>
            <Icon name="x" size={15} />
          </Button>
          <Button variant="soft" size="sm" aria-label="Cuộc trò chuyện mới" title="Cuộc trò chuyện mới" onClick={onNew} disabled={!ready}>
            <Icon name="plus" size={14} />
            Mới
          </Button>
        </div>

        <label className="search">
          <Icon name="search" size={14} />
          <span className="sr-only">Tìm phiên hội thoại</span>
          <input type="search" placeholder="Tìm phiên…" value={query} maxLength={100} onChange={(e) => onQuery(e.target.value)} />
        </label>
      </div>

      <nav className="session-list-wrap" aria-label="Các phiên hội thoại">
        {!ready ? (
          <ul className="session-list" aria-hidden="true">
            {[72, 90, 56].map((w) => (
              <li key={w}>
                <div className="session-skeleton">
                  <span className="skeleton-line" style={{ width: `${w}%` }} />
                  <span className="skeleton-line" style={{ width: '40%' }} />
                </div>
              </li>
            ))}
          </ul>
        ) : filtered.length === 0 ? (
          <div className="session-empty">
            {q ? (
              <>
                <span>Không tìm thấy phiên nào</span>
                <Button variant="quiet" size="sm" onClick={() => onQuery('')}>
                  Xoá tìm kiếm
                </Button>
              </>
            ) : (
              <span>Chưa có phiên nào. Hỏi câu đầu tiên để tạo phiên.</span>
            )}
          </div>
        ) : (
          <ol className="session-list">
            {filtered.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className={`session-item${s.id === activeId ? ' is-active' : ''}`}
                  aria-current={s.id === activeId ? 'true' : undefined}
                  aria-label={`Phiên: ${s.title}`}
                  onClick={() => onSwitch(s.id)}
                >
                  <span className="session-item-title" title={s.title}>
                    {s.title}
                  </span>
                  <span className="session-item-meta">
                    <span>{formatDate(s.updatedAt)}</span>
                    <span className="meta-dot" aria-hidden />
                    <span>{turnCount(s)} lượt</span>
                    {streaming && s.id === activeId && (
                      <span className="session-live">
                        <span className="live-dot" aria-hidden />
                        Đang trả lời
                      </span>
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </nav>

      <footer className="session-foot">
        <div className="storage">
          <div className="storage-row">
            <span>
              <strong>{sessions.length}</strong> phiên
            </span>
            {usage && (
              <span className="storage-size">
                {formatMb(usage.bytes)} / {formatMb(usage.quota)}
              </span>
            )}
          </div>
          {usage && <ProgressBar value={usage.bytes} max={usage.quota} label="Dung lượng lịch sử hội thoại" />}
          <p className="storage-note">
            <Icon name="lock" size={12} />
            Lịch sử chỉ lưu trên máy này.
          </p>
        </div>
        <Button variant="ghost" size="sm" className="manage-trigger" aria-haspopup="dialog" onClick={onManage}>
          Quản lý
          <Icon name="chevron-right" size={14} />
        </Button>
      </footer>
    </aside>
  )
}

/** Hội thoại: header tiêu đề + thao tác, empty state / log có trích dẫn, composer neo đáy. */
function ChatConversation({
  chat,
  ready,
  active,
  onToggleDrawer,
  onRename,
  onDelete,
  onOpenNote,
  onGoSettings,
  onCopy,
}: {
  chat: ChatState
  ready: boolean
  active: ChatSession | null
  onToggleDrawer: () => void
  onRename: (title: string) => void
  onDelete: () => void
  onOpenNote: (noteId: string) => void
  onGoSettings: () => void
  onCopy: (text: string) => void
}) {
  const [draft, setDraft] = useState('')
  const [renaming, setRenaming] = useState(false)
  const [renameDraft, setRenameDraft] = useState('')
  const renameId = useId()
  const folders = useAsync(() => rpc('folders/list'), [])
  const endRef = useRef<HTMLDivElement>(null)
  const last = chat.messages.at(-1)
  const streaming = chat.streaming

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' })
  }, [chat.messages.length, last?.text.length])

  // Đổi phiên → thoát chế độ đổi tên (tránh lưu nhầm tên sang phiên khác).
  useEffect(() => setRenaming(false), [active?.id])

  function send(text = draft) {
    if (!text.trim() || streaming || !ready) return
    chat.ask(text)
    setDraft('')
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    send()
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  function startRename() {
    if (!active || streaming) return
    setRenameDraft(active.title)
    setRenaming(true)
  }

  function saveRename(e: FormEvent) {
    e.preventDefault()
    if (!renameDraft.trim()) return
    onRename(renameDraft)
    setRenaming(false)
  }

  return (
    <section className="conversation" aria-labelledby="chat-conv-title">
      <div className="conv-head">
        <Button
          variant="ghost"
          size="sm"
          className="icon-only conv-drawer-toggle"
          aria-label="Mở danh sách phiên"
          title="Phiên"
          onClick={onToggleDrawer}
        >
          <Icon name="sidebar" size={17} />
        </Button>

        {renaming ? (
          <form className="rename-form" onSubmit={saveRename}>
            <label className="sr-only" htmlFor={renameId}>
              Tên cuộc trò chuyện
            </label>
            <input
              id={renameId}
              className="rename-input"
              type="text"
              value={renameDraft}
              maxLength={60}
              autoFocus
              onChange={(e) => setRenameDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') setRenaming(false)
              }}
            />
            <div className="rename-actions">
              <Button variant="ghost" size="sm" type="button" onClick={() => setRenaming(false)}>
                Huỷ
              </Button>
              <Button variant="primary" size="sm" type="submit" disabled={!renameDraft.trim()}>
                Lưu
              </Button>
            </div>
          </form>
        ) : (
          <>
            <div className="conv-title-wrap">
              {active ? (
                <>
                  <h2 className="conv-title" id="chat-conv-title" title={active.title}>
                    {active.title}
                  </h2>
                  <p className="conv-meta">
                    <span className="meta-saved">
                      <Icon name="check" size={12} />
                      Đã lưu trên máy
                    </span>
                    <span className="meta-dot" aria-hidden />
                    <span>{formatDate(active.updatedAt)}</span>
                    <span className="meta-dot" aria-hidden />
                    <span>{turnCount(active)} lượt hỏi–đáp</span>
                  </p>
                </>
              ) : (
                <>
                  <h2 className="conv-title" id="chat-conv-title">
                    Cuộc trò chuyện mới
                  </h2>
                  <p className="conv-meta">Chưa lưu · Bắt đầu bằng một câu hỏi về ghi chú của bạn.</p>
                </>
              )}
            </div>

            {active && (
              <div className="conv-actions">
                <Button variant="ghost" size="sm" onClick={startRename} disabled={streaming} title="Đổi tên cuộc trò chuyện">
                  <Icon name="edit" size={14} />
                  <span>Đổi tên</span>
                </Button>
                <Button variant="danger-ghost" size="sm" onClick={onDelete} disabled={streaming} title="Xoá cuộc trò chuyện">
                  <Icon name="trash" size={14} />
                  <span>Xoá</span>
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      <div className="conv-scroll">
        <div className="conv-body">
          {!chat.messages.length && <ChatEmptyState onPick={send} />}

          <ol className="conv-log" role="log" aria-label="Hội thoại" aria-live="off">
            {chat.messages.map((m) => {
              if (m.role === 'user') {
                return (
                  <li key={m.id} className="turn turn-user">
                    <span className="sr-only">Bạn hỏi: </span>
                    <div className="user-bubble prewrap">{m.text}</div>
                  </li>
                )
              }
              const question = previousQuestion(chat.messages, m.id)
              return (
                <AssistantMessage
                  key={m.id}
                  msg={m}
                  onOpenNote={onOpenNote}
                  onGoSettings={onGoSettings}
                  onCopy={onCopy}
                  onAskAgain={question ? () => send(question) : undefined}
                />
              )
            })}
          </ol>
          <div ref={endRef} />
        </div>
      </div>

      <p className="sr-only" aria-live="polite">
        {last?.status === 'streaming'
          ? 'Đang trả lời…'
          : last?.status === 'done'
            ? 'Đã trả lời xong.'
            : last?.status === 'stopped'
              ? 'Đã dừng trả lời.'
              : ''}
      </p>

      <form className="composer" aria-label="Hỏi AI về ghi chú" onSubmit={onSubmit}>
        <div className="composer-scope">
          <span className="scope-label">Hỏi trong</span>
          <label className="scope-select">
            <Icon name="folder" size={14} className="scope-icon" />
            <Select
              aria-label="Hỏi trong thư mục"
              value={chat.folderId ?? ''}
              disabled={streaming || !ready}
              onChange={(e) => chat.setFolderId(e.target.value || null)}
            >
              <option value="">Tất cả thư mục</option>
              {folders.data?.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </Select>
            <Icon name="chevron-down" size={13} className="scope-chevron" />
          </label>
        </div>

        <div className="composer-box">
          <TextArea
            aria-label="Câu hỏi về ghi chú"
            placeholder="Nhập câu hỏi…"
            rows={1}
            maxLength={2000}
            value={draft}
            disabled={!ready}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <div className="composer-bar">
            <span className="composer-hint">Enter để gửi · Shift+Enter xuống dòng</span>
            <div className="composer-actions">
              {streaming ? (
                <Button type="button" variant="danger-ghost" size="sm" className="btn-stop" onClick={chat.stop}>
                  <Icon name="stop" size={14} />
                  Dừng
                </Button>
              ) : (
                <Button type="submit" size="sm" disabled={!draft.trim() || !ready} title="Mỗi câu hỏi dùng hạn mức AI">
                  <Icon name="send" size={14} />
                  Gửi
                </Button>
              )}
            </div>
          </div>
        </div>
      </form>
    </section>
  )
}

/** Trạng thái trống: lời hứa "chỉ dựa trên ghi chú", 3 câu hỏi mẫu, nhắc không tự thành ghi chú. */
function ChatEmptyState({ onPick }: { onPick: (question: string) => void }) {
  return (
    <div className="conv-empty">
      <span className="empty-mark" aria-hidden="true">
        <Icon name="sparkles" size={19} />
      </span>
      <h2>Hỏi AI về ghi chú của bạn</h2>
      <p className="empty-lede">
        AI chỉ trả lời dựa trên ghi chú bạn đã lưu và ghi rõ nguồn <span className="cite-static">[1]</span>,{' '}
        <span className="cite-static">[2]</span>… để bạn kiểm tra lại. Không dùng kiến thức bên ngoài.
      </p>
      <p className="empty-label">Thử một câu hỏi</p>
      <div className="example-list">
        {EXAMPLES.map((q) => (
          <button key={q} type="button" className="example" onClick={() => onPick(q)}>
            {q}
            <Icon name="chevron-right" size={13} />
          </button>
        ))}
      </div>
      <p className="empty-foot">
        <Icon name="lock" size={13} />
        Câu trả lời không tự thành ghi chú — bạn quyết định lưu nếu thấy hữu ích.
      </p>
    </div>
  )
}

function AssistantMessage({
  msg,
  onOpenNote,
  onGoSettings,
  onCopy,
  onAskAgain,
}: {
  msg: ChatMessageItem
  onOpenNote: (noteId: string) => void
  onGoSettings: () => void
  onCopy: (text: string) => void
  onAskAgain?: () => void
}) {
  const sources = msg.sources ?? []
  const cited = new Set([...msg.text.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1])))
  const streaming = msg.status === 'streaming'
  const stopped = msg.status === 'stopped'

  return (
    <li className="turn turn-ai">
      <span className="sr-only">AI trả lời: </span>
      <div className="ai-head">
        <span className="ai-mark" aria-hidden="true">
          <Icon name="sparkles" size={13} />
        </span>
        <span className="ai-name">QuickAssist</span>
        {streaming && (
          <span className="status-pill is-live">
            <span className="status-dot" aria-hidden />
            Đang trả lời
          </span>
        )}
        {stopped && (
          <span className="status-pill is-stopped">
            <Icon name="stop" size={10} />
            Đã dừng
          </span>
        )}
        <span className="grow" />
        {msg.text && (
          <Button
            variant="ghost"
            size="sm"
            className="icon-only"
            aria-label={streaming ? 'Sao chép phần trả lời đã nhận' : 'Sao chép câu trả lời'}
            title="Sao chép câu trả lời"
            onClick={() => onCopy(msg.text)}
          >
            <Icon name="copy" size={15} />
          </Button>
        )}
      </div>

      {msg.status === 'error' && msg.error ? (
        <ErrorCard error={msg.error} onGoSettings={onGoSettings} onRetry={onAskAgain} />
      ) : (
        <div className="ai-bubble">
          {msg.text ? (
            <div className="ai-text prewrap">{withCitations(msg.text, sources, onOpenNote)}</div>
          ) : (
            streaming && <span className="muted">Đang tìm trong ghi chú…</span>
          )}
          {streaming && msg.text && <span className="caret" aria-hidden="true" />}

          {stopped && (
            <div className="answer-foot answer-foot-stopped">
              <span>Bạn đã dừng câu trả lời này. Phần đã nhận vẫn được giữ trong phiên.</span>
              {onAskAgain && (
                <Button variant="ghost" size="sm" onClick={onAskAgain}>
                  Hỏi lại
                </Button>
              )}
            </div>
          )}
          {msg.status === 'done' && msg.text && (
            <div className="answer-foot">
              <Icon name="check" size={13} />
              Chỉ dùng nội dung trong ghi chú của bạn — không thêm kiến thức ngoài.
            </div>
          )}

          {sources.length > 0 && <Sources sources={sources} cited={cited} streaming={streaming} onOpenNote={onOpenNote} />}
        </div>
      )}
    </li>
  )
}

/** Hàng chip nguồn + `Chi tiết nguồn` (khoá đến khi câu trả lời xong vì snippet có thể chưa sẵn sàng). */
function Sources({
  sources,
  cited,
  streaming,
  onOpenNote,
}: {
  sources: ChatSource[]
  cited: Set<number>
  streaming: boolean
  onOpenNote: (noteId: string) => void
}) {
  const titleOf = (s: ChatSource) => s.title ?? 'Ghi chú'
  return (
    <div className="sources">
      <div className="source-row">
        <span className="source-label">Nguồn ({sources.length})</span>
        <div className="source-chips">
          {sources.map((s) => (
            <button
              key={s.chunk_id}
              type="button"
              className={`source-chip${cited.has(s.index) ? ' is-cited' : ''}`}
              title={titleOf(s)}
              aria-label={`Nguồn ${s.index}: ${titleOf(s)}`}
              onClick={() => onOpenNote(s.note_id)}
            >
              <span className="chip-index">[{s.index}]</span>
              <span className="chip-title">{titleOf(s)}</span>
            </button>
          ))}
        </div>
      </div>

      {streaming ? (
        <p className="source-pending">Nguồn đã sẵn sàng — chi tiết mở khi câu trả lời hoàn tất.</p>
      ) : (
        <details className="source-more">
          <summary>
            <Icon name="chevron-right" size={11} />
            Chi tiết nguồn
          </summary>
          <ul className="source-cards">
            {sources.map((s) => (
              <li key={s.chunk_id} className="source-card">
                <span className="source-index" aria-hidden="true">
                  [{s.index}]
                </span>
                <div className="source-body">
                  <p className="source-title">{titleOf(s)}</p>
                  <p className="source-snippet">{s.snippet}</p>
                  <div className="source-actions">
                    <Button variant="quiet" size="sm" onClick={() => onOpenNote(s.note_id)}>
                      Mở ghi chú
                    </Button>
                    {s.url && (
                      <a className="link-quiet" href={s.url} target="_blank" rel="noreferrer noopener">
                        Trang nguồn
                        <Icon name="external" size={11} />
                      </a>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

/** Card lỗi theo `SerializedError`: hạn mức → "Xem hạn mức"; lỗi có thể thử lại → "Thử lại". */
function ErrorCard({ error, onGoSettings, onRetry }: { error: SerializedError; onGoSettings: () => void; onRetry?: () => void }) {
  const quota = error.code === 'QUOTA_EXCEEDED'
  const retryable = !quota && (error.status === 0 || error.status === 429 || error.status >= 500)
  return (
    <div className="ai-error" role="alert">
      <span className="error-mark" aria-hidden="true">
        <Icon name="alert" size={16} />
      </span>
      <div className="error-body">
        <h3>{quota ? 'Đã hết hạn mức AI' : 'Không trả lời được'}</h3>
        <p>{userMessage(error)}</p>
        <div className="error-actions">
          {quota && (
            <Button size="sm" onClick={onGoSettings}>
              Xem hạn mức
            </Button>
          )}
          {retryable && onRetry && (
            <Button variant="ghost" size="sm" onClick={onRetry}>
              Thử lại
            </Button>
          )}
        </div>
        {error.requestId && <small className="muted">Mã lỗi: {error.requestId}</small>}
      </div>
    </div>
  )
}

/** Thay "[n]" trong câu trả lời bằng nút mở ghi chú nguồn tương ứng (nếu n là nguồn có thật). */
export function withCitations(text: string, sources: ChatSource[], onOpenNote: (noteId: string) => void): ReactNode[] {
  const byIndex = new Map(sources.map((s) => [s.index, s]))
  return text.split(/(\[\d+\])/g).map((part, i) => {
    const m = /^\[(\d+)\]$/.exec(part)
    const src = m ? byIndex.get(Number(m[1])) : undefined
    if (!src) return part
    return (
      <button
        key={i}
        type="button"
        className="cite"
        title={`Mở ghi chú: ${src.title ?? 'Ghi chú'}`}
        aria-label={`Mở ghi chú nguồn ${src.index}: ${src.title ?? 'Ghi chú'}`}
        onClick={() => onOpenNote(src.note_id)}
      >
        [{src.index}]
      </button>
    )
  })
}
