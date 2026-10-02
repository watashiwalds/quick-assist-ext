/**
 * Ghi chú nhanh (kịch bản #1): selection → toast 5s có Hoàn tác → gửi server.
 *
 * Thiết kế bền vững với việc service worker MV3 bị tắt bất kỳ lúc nào:
 * ghi chú vào OUTBOX (IndexedDB) NGAY khi người dùng thao tác, kèm `notBefore`
 * = now + 5s. Hoàn tác = xoá khỏi outbox. Gửi = flush các mục đến hạn; lỗi mạng
 * thì giữ lại, alarm 1 phút sẽ thử lại. Idempotency-Key = id mục outbox → không trùng.
 */
import type { NoteCreate } from '@/shared/api/types'
import { config } from '@/shared/config'
import { AppError } from '@/shared/errors'
import { outbox } from '@/shared/storage/db'
import { api } from '../api'
import { broadcast } from '../broadcast'
import { showToast } from '../page-actions'
import { notesCacheAfterCreate } from './sync'

export const FLUSH_ALARM = 'qa.outbox.flush'
const MAX_ATTEMPTS = 8

export async function startQuickNote(tabId: number, sel: { text: string; url?: string; title?: string }) {
  const text = sel.text.trim()
  if (!text) {
    await showToast(tabId, { kind: 'error', message: 'Hãy bôi đen đoạn văn bản cần ghi chú.' })
    return
  }
  const id = crypto.randomUUID()
  const body: NoteCreate = {
    content: text,
    url: sel.url?.startsWith('http') ? sel.url : null,
    title: sel.title?.slice(0, 500) ?? null,
  }
  await outbox.put({ id, body, notBefore: Date.now() + config.undoWindowMs, attempts: 0, createdAt: Date.now() })
  await showToast(tabId, { kind: 'pending', pendingId: id, snippet: text.slice(0, 140), seconds: config.undoWindowMs / 1000 })
  setTimeout(() => void flushOutbox(), config.undoWindowMs + 200)
}

export async function undoQuickNote(pendingId: string): Promise<boolean> {
  // Chỉ hoàn tác được khi chưa gửi (mục còn trong outbox).
  return outbox.remove(pendingId)
}

let flushing = false

export async function flushOutbox(): Promise<void> {
  if (flushing) return
  flushing = true
  try {
    for (const item of await outbox.due()) {
      try {
        const note = await api.notes.create(item.body, item.id)
        await outbox.remove(item.id)
        await notesCacheAfterCreate(note)
        broadcast({ channel: 'qa-event', type: 'notes/changed' })
      } catch (e) {
        const err = e instanceof AppError ? e : new AppError('UNKNOWN', String(e))
        if (err.retryable && item.attempts + 1 < MAX_ATTEMPTS) {
          const backoff = Math.min(2 ** item.attempts * 10_000, 15 * 60_000)
          await outbox.put({ ...item, attempts: item.attempts + 1, lastError: err.code, notBefore: Date.now() + backoff })
        } else {
          // Lỗi không thể thử lại (validation, hết phiên...) → bỏ khỏi outbox, báo người dùng.
          // TODO(N06): lưu sang "failed" store để UI cho phép sửa/gửi lại thủ công.
          await outbox.remove(item.id)
        }
      }
    }
  } finally {
    flushing = false
  }
}
