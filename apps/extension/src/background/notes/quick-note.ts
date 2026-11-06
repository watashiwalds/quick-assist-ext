/**
 * Ghi chú nhanh (kịch bản #1): selection → toast 5s có Hoàn tác → gửi server.
 *
 * Thiết kế bền vững với việc service worker MV3 bị tắt bất kỳ lúc nào:
 * ghi chú vào OUTBOX (IndexedDB) NGAY khi người dùng thao tác, kèm `notBefore`
 * = now + 5s. Hoàn tác = xoá khỏi outbox. Gửi = flush các mục đến hạn; lỗi mạng/5xx/429
 * thì giữ lại, alarm 1 phút sẽ thử lại (backoff). Lỗi không tự khắc phục (413, 422, hết
 * phiên, quá số lần thử) → chuyển sang store "failed" để người dùng Gửi lại / Bỏ (N06) —
 * KHÔNG BAO GIỜ âm thầm xoá ghi chú. Idempotency-Key = id mục outbox → không trùng.
 */
import type { Note, NoteCreate } from '@/shared/api/types'
import { config } from '@/shared/config'
import { AppError } from '@/shared/errors'
import type { PendingNote } from '@/shared/messaging/protocol'
import { failedStore, type OutboxItem, outbox } from '@/shared/storage/db'
import { api } from '../api'
import { hasSession } from '../auth/session'
import { broadcast } from '../broadcast'
import { cachedFolders } from '../menus'
import { showToast } from '../page-actions'
import { getPrefs } from '../prefs'
import { notesCacheAfterCreate } from './sync'

export const FLUSH_ALARM = 'qa.outbox.flush'
export const MAX_ATTEMPTS = 8

export interface Selection {
  text: string
  url?: string
  title?: string
}

/** Bắt đầu lưu nhanh. folderId undefined → thư mục mặc định trong Cài đặt (mặc định Inbox). */
export async function startQuickNote(tabId: number, sel: Selection, folderId?: string | null): Promise<string | null> {
  const raw = sel.text.trim()
  if (!raw) {
    await showToast(tabId, { kind: 'error', message: 'Hãy bôi đen đoạn văn bản cần ghi chú.' })
    return null
  }
  if (!(await hasSession())) {
    await showToast(tabId, { kind: 'error', message: 'Hãy đăng nhập QuickAssist (biểu tượng trên thanh công cụ) để lưu ghi chú.' })
    return null
  }
  const truncated = raw.length > config.maxNoteChars
  const text = raw.slice(0, config.maxNoteChars)
  const target = folderId === undefined ? (await getPrefs()).defaultFolderId : folderId
  const folders = await cachedFolders()
  const folder = target ? folders.find((f) => f.id === target) : undefined

  const id = crypto.randomUUID()
  const body: NoteCreate = {
    content: text,
    url: sel.url?.startsWith('http') ? sel.url : null,
    title: sel.title?.slice(0, 500) || null,
    ...(folder ? { folder_id: folder.id } : {}), // thư mục không còn trong cache → Inbox
  }
  await outbox.put({ id, body, notBefore: Date.now() + config.undoWindowMs, attempts: 0, createdAt: Date.now() })
  broadcast({ channel: 'qa-event', type: 'outbox/changed' })
  await showToast(tabId, {
    kind: 'pending',
    pendingId: id,
    snippet: text.slice(0, 140),
    seconds: config.undoWindowMs / 1000,
    folderName: folder?.name ?? 'Inbox',
    note: truncated ? `Đã cắt còn ${config.maxNoteChars.toLocaleString('vi-VN')} ký tự đầu.` : undefined,
  })
  setTimeout(() => void flushOutbox(), config.undoWindowMs + 200)
  return id
}

export async function undoQuickNote(pendingId: string): Promise<boolean> {
  // Chỉ hoàn tác được khi chưa gửi (mục còn trong outbox).
  const undone = await outbox.remove(pendingId)
  if (undone) broadcast({ channel: 'qa-event', type: 'outbox/changed' })
  return undone
}

/** Lỗi nào thì giữ trong outbox để tự gửi lại; lỗi nào phải hỏi người dùng. */
export function classify(err: AppError, attempts: number): 'retry' | 'fail' {
  if (err.code === 'TOKEN_MISSING' || err.status === 401) return 'fail' // hết phiên → đăng nhập lại rồi "Gửi lại"
  if (err.retryable && attempts + 1 < MAX_ATTEMPTS) return 'retry'
  return 'fail'
}

export function backoffMs(attempts: number): number {
  return Math.min(2 ** attempts * 10_000, 15 * 60_000) // 10s, 20s, 40s … tối đa 15'
}

let flushing: Promise<void> | null = null

export function flushOutbox(): Promise<void> {
  flushing ??= doFlush().finally(() => {
    flushing = null
  })
  return flushing
}

async function doFlush(): Promise<void> {
  const due = await outbox.due()
  if (due.length === 0) return
  if (!(await hasSession())) return // giữ nguyên, gửi khi đăng nhập lại
  let changed = false
  for (const item of due) {
    if (!(await outbox.get(item.id))) continue // vừa bị hoàn tác
    try {
      const note: Note = await api.notes.create(item.body, item.id)
      await outbox.remove(item.id)
      await notesCacheAfterCreate(note)
      broadcast({ channel: 'qa-event', type: 'notes/changed' })
    } catch (e) {
      const err = e instanceof AppError ? e : new AppError('UNKNOWN', String(e))
      if (err.code === 'FOLDER_NOT_FOUND' && item.body.folder_id) {
        // Thư mục đã bị xoá ở máy khác → lưu vào Inbox thay vì mất ghi chú.
        const { folder_id: _f, ...rest } = item.body
        await outbox.put({ ...item, body: rest, notBefore: Date.now() })
      } else if (classify(err, item.attempts) === 'retry') {
        await outbox.put({ ...item, attempts: item.attempts + 1, lastError: err.code, notBefore: Date.now() + backoffMs(item.attempts) })
      } else {
        await failedStore.moveFromOutbox(item, err.code)
      }
    }
    changed = true
  }
  if (changed) broadcast({ channel: 'qa-event', type: 'outbox/changed' })
}

function toPending(i: OutboxItem, state: PendingNote['state']): PendingNote {
  return {
    id: i.id,
    snippet: i.body.content.slice(0, 160),
    url: i.body.url ?? null,
    title: i.body.title ?? null,
    folderId: i.body.folder_id ?? null,
    createdAt: i.createdAt,
    attempts: i.attempts,
    lastError: i.lastError,
    state,
  }
}

export async function listPending(): Promise<PendingNote[]> {
  const [queued, failed] = await Promise.all([outbox.list(), failedStore.list()])
  return [...failed.map((i) => toPending(i, 'failed')), ...queued.map((i) => toPending(i, 'queued'))].sort(
    (a, b) => b.createdAt - a.createdAt,
  )
}

export async function retryPending(id: string): Promise<void> {
  if (!(await failedStore.requeue(id))) {
    const q = await outbox.get(id) // mục đang chờ backoff → gửi ngay
    if (q) await outbox.put({ ...q, notBefore: Date.now() })
  }
  broadcast({ channel: 'qa-event', type: 'outbox/changed' })
  await flushOutbox()
}

export async function discardPending(id: string): Promise<void> {
  await failedStore.remove(id)
  await outbox.remove(id)
  broadcast({ channel: 'qa-event', type: 'outbox/changed' })
}
