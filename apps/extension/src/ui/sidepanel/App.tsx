/** Side panel — khung ứng dụng chính: Thư viện · Tìm kiếm · Hỏi AI · Tóm tắt (khi có vùng chọn) · Cài đặt. */
import { useEffect, useState } from 'react'
import { rpc } from '@/shared/messaging/client'
import type { PendingSelection } from '@/shared/messaging/protocol'
import { type TabItem, Tabs, ToastProvider } from '../components'
import { SettingsView } from '../features/account/SettingsView'
import { AuthGate } from '../features/auth/AuthGate'
import { ChatView } from '../features/chat/ChatView'
import { useChat } from '../features/chat/useChat'
import { NotesView } from '../features/notes/NotesView'
import { SearchView } from '../features/search/SearchView'
import { SelectionSummary } from '../features/summary/SelectionSummary'
import { useAsync, useBroadcast } from '../lib/hooks'

type Tab = 'notes' | 'search' | 'chat' | 'summary' | 'settings'

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
  const chat = useChat() // giữ hội thoại khi chuyển tab; câu trả lời đang stream vẫn chạy tiếp

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

  const items: TabItem<Tab>[] = [
    { key: 'notes', label: 'Thư viện' },
    { key: 'search', label: 'Tìm kiếm' },
    { key: 'chat', label: 'Hỏi AI' },
    ...(selection ? [{ key: 'summary' as const, label: 'Tóm tắt' }] : []),
    { key: 'settings', label: 'Cài đặt' },
  ]
  const goSettings = () => setTab('settings')

  return (
    <>
      <header className="header">
        <strong>QuickAssist</strong>
        <span className="muted ellipsis">{session.user?.email}</span>
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
        {tab === 'chat' && (
          <ChatView
            chat={chat}
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
        {tab === 'settings' && <SettingsView session={session} />}
      </main>
    </>
  )
}
