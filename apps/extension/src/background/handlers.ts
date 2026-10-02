/**
 * Bảng định tuyến RPC: mỗi khoá trong RpcMap ↔ đúng 1 handler.
 * Kiểu `Handlers` bắt buộc ĐỦ handler cho mọi RPC — thiếu là lỗi biên dịch.
 */
import { AppError } from '@/shared/errors'
import type { RpcMap, RpcReq, RpcRes, RpcType, SessionInfo } from '@/shared/messaging/protocol'
import { notesCache } from '@/shared/storage/db'
import { api } from './api'
import { loginWithGoogle } from './auth/google'
import { clearTokens, hasSession, logoutRemote } from './auth/session'
import { broadcast } from './broadcast'
import { undoQuickNote } from './notes/quick-note'
import { syncNotes } from './notes/sync'

type Handlers = { [K in RpcType]: (req: RpcReq<K>) => Promise<RpcRes<K>> }

async function sessionInfo(): Promise<SessionInfo> {
  if (!(await hasSession())) return { signedIn: false, user: null }
  try {
    return { signedIn: true, user: await api.me.get() }
  } catch (e) {
    if (e instanceof AppError && e.status === 401) {
      await clearTokens()
      return { signedIn: false, user: null }
    }
    throw e
  }
}

async function signedOut(): Promise<SessionInfo> {
  await notesCache.clear() // không để dữ liệu người trước trên máy dùng chung
  broadcast({ channel: 'qa-event', type: 'session/changed', signedIn: false })
  return { signedIn: false, user: null }
}

export const handlers: Handlers = {
  'auth/status': () => sessionInfo(),
  'auth/login': async () => {
    await loginWithGoogle()
    broadcast({ channel: 'qa-event', type: 'session/changed', signedIn: true })
    return sessionInfo()
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

  'folders/list': () => api.folders.list(),
  'folders/create': ({ name }) => api.folders.create(name),
  'folders/delete': async ({ id }) => {
    await api.folders.remove(id)
    await syncNotes() // note đã được chuyển về Inbox
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
  'notes/reindex': ({ id }) => api.notes.reindex(id),

  'quickNote/undo': async ({ pendingId }) => ({ undone: await undoQuickNote(pendingId) }),

  'search/query': async ({ query, folderId }) => (await api.search.query({ query, folder_id: folderId })).items,
  'summary/preview': ({ noteId, text }) => api.ai.summarize(noteId ? { note_id: noteId } : { text }),
  'summary/save': async ({ noteId, version, summary }) => {
    const note = await api.notes.saveSummary(noteId, version, summary)
    await notesCache.apply([note])
    return note
  },
}

export async function dispatch<K extends RpcType>(type: K, payload: RpcReq<K>): Promise<RpcRes<K>> {
  const h = handlers[type] as ((req: RpcMap[K]['req']) => Promise<RpcRes<K>>) | undefined
  if (!h) throw new AppError('UNKNOWN_RPC', `RPC không tồn tại: ${String(type)}`)
  return h(payload)
}
