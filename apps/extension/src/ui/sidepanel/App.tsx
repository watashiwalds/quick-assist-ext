/** Side panel — khung ứng dụng chính: Thư viện (tìm nhanh + tìm sâu AI) · Tìm kiếm* · Tìm trong trang · Hỏi AI · Tóm tắt (khi có vùng chọn) · Cài đặt. Tab "Tìm kiếm" ẩn mặc định, bật lại trong Cài đặt. */
import { useEffect, useState } from 'react'
import { rpc } from '@/shared/messaging/client'
import type { PendingSelection } from '@/shared/messaging/protocol'
import { type TabItem, Icon, Tabs, ToastProvider } from '../components'
import { SettingsView } from '../features/account/SettingsView'
import { AuthGate } from '../features/auth/AuthGate'
import { ChatView } from '../features/chat/ChatView'
import { useChatSessions } from '../features/chat/useChatSessions'
import { NotesView } from '../features/notes/NotesView'
import { PageFinderView } from '../features/page-finder/PageFinderView'
import { SearchView } from '../features/search/SearchView'
import { SelectionSummary } from '../features/summary/SelectionSummary'
import { useAsync, useBroadcast } from '../lib/hooks'

type Tab = 'notes' | 'search' | 'page' | 'chat' | 'summary' | 'settings'

export function App() {
  return (
    <ToastProvider>
      <div className="app">
        <AuthGate>{(session) => <Shell session={session} />}</AuthGate>
      </div>
    </ToastProvider>
  )
}

function Shell({ session }: { session: Parameters<typeof SettingsView>[0]['session'] }) {
  const [tab, setTab] = useState<Tab>('notes')
  const [openNoteId, setOpenNoteId] = useState<string | null>(null)
  const [selection, setSelection] = useState<PendingSelection | null>(null)
  const folders = useAsync(() => rpc('folders/list'), [])
  const prefs = useAsync(() => rpc('prefs/get'), [])
  const showSearchTab = prefs.data?.showSearchTab ?? false
  const chat = useChatSessions() // giữ hội thoại khi chuyển tab; lưu nhiều phiên trên trình duyệt

  // Đóng side panel giữa stream: ghi nốt phần đã nhận (stream không thể tiếp tục khi mở lại).
  useEffect(() => {
    const flush = () => chat.flush()
    window.addEventListener('pagehide', flush)
    return () => window.removeEventListener('pagehide', flush)
  }, [chat.flush])

  const takeSelection = () =>
    void rpc('selection/takePending').then((s) => {
      if (!s) return
      setSelection(s)
      setTab('summary')
    })
  useEffect(takeSelection, [])
  useBroadcast((e) => {
    if (e.type === 'selection/pending') takeSelection()
    if (e.type === 'folders/changed') void folders.reload()
  })

  // Tab "Tìm kiếm" bị tắt trong Cài đặt khi đang mở → về Thư viện.
  useEffect(() => {
    if (tab === 'search' && prefs.data && !showSearchTab) setTab('notes')
  }, [tab, prefs.data, showSearchTab])

  const items: TabItem<Tab>[] = [
    { key: 'notes', label: 'Thư viện' },
    ...(showSearchTab ? [{ key: 'search' as const, label: 'Tìm kiếm' }] : []),
    { key: 'page', label: 'Tìm trong trang' },
    { key: 'chat', label: 'Hỏi AI' },
    ...(selection ? [{ key: 'summary' as const, label: 'Tóm tắt' }] : []),
    { key: 'settings', label: 'Cài đặt' },
  ]
  const goSettings = () => setTab('settings')

  return (
    <>
      <header className="header">
        <span className="brand">
          <span className="brand-mark" aria-hidden>
            <Icon name="note" size={16} />
          </span>
          <strong className="brand-name">QuickAssist</strong>
        </span>
        <span className="grow" />
        <span className="user" title={session.user?.email}>
          <span className="avatar" aria-hidden>
            <Icon name="user" size={14} />
          </span>
          <span className="email">{session.user?.email}</span>
        </span>
      </header>
      <Tabs items={items} value={tab} onChange={setTab} />
      <main className="content" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'notes' && <NotesView openNoteId={openNoteId} onOpened={() => setOpenNoteId(null)} onGoSettings={goSettings} />}
        {tab === 'search' && (
          <SearchView
            onGoSettings={goSettings}
            onOpenNote={(id) => {
              setOpenNoteId(id)
              setTab('notes')
            }}
          />
        )}
        {tab === 'page' && <PageFinderView folders={folders.data ?? []} onGoSettings={goSettings} />}
        {tab === 'chat' && (
          <ChatView
            chat={chat}
            sessions={chat.sessions}
            activeId={chat.activeId}
            onSwitchSession={chat.switchSession}
            onNewSession={chat.newSession}
            onGoSettings={goSettings}
            onOpenNote={(id) => {
              setOpenNoteId(id)
              setTab('notes')
            }}
          />
        )}
        {tab === 'summary' && (
          <SelectionSummary
            selection={selection}
            folders={folders.data ?? []}
            onGoSettings={goSettings}
            onDone={() => {
              setSelection(null)
              setTab('notes')
            }}
          />
        )}
        {tab === 'settings' && <SettingsView session={session} onPrefsChanged={prefs.setData} />}
      </main>
    </>
  )
}
