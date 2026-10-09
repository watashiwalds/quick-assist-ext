/**
 * Đồng bộ tăng dần server → IndexedDB (kịch bản #3 "Duyệt note", cache-first).
 * GET /notes?updated_since=<lastSyncAt> trả cả tombstone (deleted_at) để xoá local.
 * Xung đột ghi: server là nguồn sự thật; PATCH gửi kèm version, 409 → UI hỏi người dùng.
 */
import type { Note } from '@/shared/api/types'
import { meta, notesCache } from '@/shared/storage/db'
import { api } from '../api'

let running: Promise<number> | null = null

/** Single-flight: nhiều màn hình cùng yêu cầu sync chỉ chạy MỘT lượt. */
export function syncNotes(): Promise<number> {
  running ??= doSync().finally(() => {
    running = null
  })
  return running
}

export const LAST_SYNC = 'notes.lastSyncAt'

async function doSync(): Promise<number> {
  const since = await meta.get(LAST_SYNC)
  let cursor: string | undefined
  let changed = 0
  let maxUpdated = since ?? ''
  do {
    const page = await api.notes.list({ updated_since: since, cursor, limit: 200 })
    await notesCache.apply(page.items)
    changed += page.items.length
    // So sánh theo thời gian (không theo chuỗi: "…:43Z" vs "…:43.5Z" sai thứ tự từ điển).
    for (const n of page.items) if (!maxUpdated || Date.parse(n.updated_at) > Date.parse(maxUpdated)) maxUpdated = n.updated_at
    cursor = page.next_cursor ?? undefined
  } while (cursor)
  if (maxUpdated) await meta.set(LAST_SYNC, maxUpdated)
  return changed
}

export async function notesCacheAfterCreate(note: Note): Promise<void> {
  await notesCache.apply([note])
}
