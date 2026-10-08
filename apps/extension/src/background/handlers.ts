/**
 * Bảng định tuyến RPC: mỗi khoá trong RpcMap ↔ đúng 1 handler.
 * Kiểu `Handlers` bắt buộc ĐỦ handler cho mọi RPC — thiếu là lỗi biên dịch.
 */
import { createHttp } from '@/shared/api/http'
import type { TokenPair } from '@/shared/api/types'
import { config } from '@/shared/config'
import { AppError } from '@/shared/errors'
import type { RpcMap, RpcReq, RpcRes, RpcType, SessionInfo } from '@/shared/messaging/protocol'
import { notesCache } from '@/shared/storage/db'
import { api } from './api'
import { loginWithGoogle } from './auth/google'
import { clearTokens, hasSession, logoutRemote, saveTokens } from './auth/session'
import { broadcast } from './broadcast'
import { rememberFolders } from './menus'
import { discardPending, flushOutbox, listPending, retryPending, undoQuickNote } from './notes/quick-note'
import { syncNotes } from './notes/sync'
import { clearPrefs, getPrefs, setPrefs } from './prefs'
import { takePendingSelection } from './selection'

type Handlers = { [K in RpcType]: (req: RpcReq<K>) => Promise<RpcRes<K>> }

const USER_KEY = 'qa.user'

async function sessionInfo(): Promise<SessionInfo> {
  if (!(await hasSession())) return { signedIn: false, user: null }
  try {
    const user = await api.me.get()
    await chrome.storage.local.set({ [USER_KEY]: user })
    return { signedIn: true, user }
  } catch (e) {
    if (e instanceof AppError && (e.status === 401 || e.status === 404)) {
      await clearTokens()
      return { signedIn: false, user: null }
    }
    // Mất mạng / máy chủ lỗi: vẫn cho mở thư viện từ cache (ADR-0008) với hồ sơ đã lưu.
    const cached = (await chrome.storage.local.get(USER_KEY))[USER_KEY] as SessionInfo['user'] | undefined
    if (cached && e instanceof AppError && e.retryable) return { signedIn: true, user: cached }
    throw e
  }
}

async function signedIn(): Promise<SessionInfo> {
  broadcast({ channel: 'qa-event', type: 'session/changed', signedIn: true })
  await refreshFolders().catch(() => undefined) // menu "Ghi chú vào thư mục"
  void flushOutbox() // ghi chú chờ từ trước (vd. phiên cũ hết hạn)
  return sessionInfo()
}

async function signedOut(): Promise<SessionInfo> {
  // Không để dữ liệu người trước trên máy dùng chung (R-10): cache, outbox, failed, meta, prefs, hồ sơ.
  await notesCache.clear()
  await chrome.storage.local.remove(USER_KEY)
  await clearPrefs()
  await rememberFolders([])
  broadcast({ channel: 'qa-event', type: 'session/changed', signedIn: false })
  return { signedIn: false, user: null }
}

async function refreshFolders() {
  const folders = await api.folders.list()
  await rememberFolders(folders)
  return folders
}

async function folderChanged<T>(p: Promise<T>): Promise<T> {
  const r = await p
  await refreshFolders()
  broadcast({ channel: 'qa-event', type: 'folders/changed' })
  return r
}

export const handlers: Handlers = {
  'auth/status': () => sessionInfo(),
  'auth/login': async () => {
    await loginWithGoogle()
    return signedIn()
  },
  'auth/logout': async () => {
    await logoutRemote()
    return signedOut()
  },
  'account/delete': async () => {
    await api.me.delete()
    await clearTokens()
    return signedOut()
  },
  'quota/get': () => api.me.quota(),

  'prefs/get': () => getPrefs(),
  'prefs/set': (patch) => setPrefs(patch),

  'folders/list': () => refreshFolders(),
  'folders/create': ({ name }) => folderChanged(api.folders.create(name)),
  'folders/rename': ({ id, name }) => folderChanged(api.folders.rename(id, name)),
  'folders/delete': async ({ id }) => {
    await folderChanged(api.folders.remove(id))
    const prefs = await getPrefs()
    if (prefs.defaultFolderId === id) await setPrefs({ defaultFolderId: null })
    await syncNotes() // note đã được chuyển về Inbox
    broadcast({ channel: 'qa-event', type: 'notes/changed' })
  },

  'notes/list': async ({ folderId }) => {
    // Cache-first: trả cache ngay nếu có; đồng bộ nền rồi phát 'notes/changed'.
    const cached = await notesCache.list(folderId)
    const sync = syncNotes().then((n) => n > 0 && broadcast({ channel: 'qa-event', type: 'notes/changed' }))
    if (cached.length > 0) {
      sync.catch(() => undefined)
      return cached
    }
    await sync
    return notesCache.list(folderId)
  },
  'notes/get': async ({ id }) => {
    const note = await api.notes.get(id)
    await notesCache.apply([note])
    return note
  },
  'notes/sync': async () => ({ changed: await syncNotes() }),
  'notes/update': async ({ id, version, content, title, folderId }) => {
    const note = await api.notes.update(id, { version, content, title, folder_id: folderId })
    await notesCache.apply([note])
    return note
  },
  'notes/delete': async ({ ids }) => {
    const res = ids.length === 1 ? (await api.notes.remove(ids[0]!), { deleted: 1 }) : await api.notes.bulkDelete(ids)
    await notesCache.remove(ids)
    return res
  },
  'notes/reindex': async ({ id }) => {
    const note = await api.notes.reindex(id)
    await notesCache.apply([note])
    return note
  },

  'quickNote/undo': async ({ pendingId }) => ({ undone: await undoQuickNote(pendingId) }),
  'outbox/list': () => listPending(),
  'outbox/retry': ({ id }) => retryPending(id),
  'outbox/discard': ({ id }) => discardPending(id),

  'search/query': async ({ query, folderId }) => (await api.search.query({ query, folder_id: folderId })).items,
  'summary/preview': ({ noteId, text }) =>
    api.ai.summarize(noteId ? { note_id: noteId } : { text: (text ?? '').slice(0, config.maxSummaryChars) }),
  'summary/save': async ({ noteId, version, summary }) => {
    const note = await api.notes.saveSummary(noteId, version, summary)
    await notesCache.apply([note])
    return note
  },
  'summary/saveSelection': async ({ text, url, title, summary, folderId }) => {
    const created = await api.notes.create(
      { content: text.slice(0, config.maxNoteChars), url: url ?? null, title: title ?? null, ...(folderId ? { folder_id: folderId } : {}) },
      crypto.randomUUID(),
    )
    const note = await api.notes.saveSummary(created.id, created.version, summary)
    await notesCache.apply([note])
    broadcast({ channel: 'qa-event', type: 'notes/changed' })
    return note
  },
  'selection/takePending': () => takePendingSelection(),

  'e2e/devLogin': async ({ email }) => {
    if (import.meta.env.VITE_E2E !== 'true') throw new AppError('E2E_ONLY', 'Chỉ có trong bản build kiểm thử')
    // Gọi thẳng (không qua endpoints.ts) để bản phát hành không chứa đường dẫn này.
    await saveTokens(await createHttp()<TokenPair>('/auth/dev-login', { method: 'POST', body: { email } }))
    return signedIn()
  },
}

export async function dispatch<K extends RpcType>(type: K, payload: RpcReq<K>): Promise<RpcRes<K>> {
  const h = handlers[type] as ((req: RpcMap[K]['req']) => Promise<RpcRes<K>>) | undefined
  if (!h) throw new AppError('UNKNOWN_RPC', `RPC không tồn tại: ${String(type)}`)
  return h(payload)
}
