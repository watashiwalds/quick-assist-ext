import { useState } from 'react'
import { rpc } from '@/shared/messaging/client'
import { Button } from '../components'
import { AuthGate } from '../features/auth/AuthGate'
import { NotesView } from '../features/notes/NotesView'
import { SearchView } from '../features/search/SearchView'

type Tab = 'notes' | 'search'

export function App() {
  const [tab, setTab] = useState<Tab>('notes')
  return (
    <div className="app">
      <AuthGate>
        {(session) => (
          <>
            <header className="header">
              <strong>QuickAssist</strong>
              <div className="row">
                <span className="muted">{session.user?.email}</span>
                <Button variant="ghost" onClick={() => void rpc('auth/logout')}>
                  Đăng xuất
                </Button>
              </div>
            </header>
            <nav className="tabs" role="tablist">
              <Button variant="ghost" role="tab" aria-selected={tab === 'notes'} onClick={() => setTab('notes')}>
                Thư viện
              </Button>
              <Button variant="ghost" role="tab" aria-selected={tab === 'search'} onClick={() => setTab('search')}>
                Tìm kiếm
              </Button>
            </nav>
            <main className="content">{tab === 'notes' ? <NotesView /> : <SearchView />}</main>
          </>
        )}
      </AuthGate>
    </div>
  )
}
