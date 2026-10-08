/**
 * IndexedDB local (ADR-0008):
 *  - notes   : cache đọc (stale-while-revalidate) — nguồn sự thật vẫn là server.
 *  - outbox  : hàng đợi ghi chú chưa gửi được (mất mạng / đang trong 5s hoàn tác).
 *  - failed  : ghi chú gửi lỗi không tự khắc phục (413, 422, hết phiên…) — chờ người dùng
 *              "Gửi lại" hoặc "Bỏ" (N06). Không bao giờ tự xoá → không mất ghi chú.
 *  - meta    : con trỏ đồng bộ (lastSyncAt), cache danh sách thư mục cho menu chuột phải.
 * Chỉ background ghi vào DB này; UI đọc qua RPC.
 */
import { type DBSchema, type IDBPDatabase, openDB } from 'idb'
import type { Note, NoteCreate } from '../api/types'

export interface OutboxItem {
  id: string // = Idempotency-Key → retry không tạo trùng
  body: NoteCreate
  notBefore: number // epoch ms; hết cửa sổ hoàn tác mới gửi
  attempts: number
  lastError?: string
  createdAt: number
}

export interface FailedItem extends OutboxItem {
  failedAt: number
}

interface QADB extends DBSchema {
  notes: { key: string; value: Note; indexes: { by_folder: string; by_updated: string } }
  outbox: { key: string; value: OutboxItem; indexes: { by_notBefore: number } }
  failed: { key: string; value: FailedItem }
  meta: { key: string; value: { key: string; value: string } }
}

let dbp: Promise<IDBPDatabase<QADB>> | null = null

export function db(): Promise<IDBPDatabase<QADB>> {
  dbp ??= openDB<QADB>('quickassist', 2, {
    upgrade(d, oldVersion) {
      if (oldVersion < 1) {
        const notes = d.createObjectStore('notes', { keyPath: 'id' })
        notes.createIndex('by_folder', 'folder_id')
        notes.createIndex('by_updated', 'updated_at')
        d.createObjectStore('outbox', { keyPath: 'id' }).createIndex('by_notBefore', 'notBefore')
        d.createObjectStore('meta', { keyPath: 'key' })
      }
      if (oldVersion < 2) d.createObjectStore('failed', { keyPath: 'id' })
    },
  })
  return dbp
}

export const notesCache = {
  async list(folderId?: string | null): Promise<Note[]> {
    const d = await db()
    const rows = folderId ? await d.getAllFromIndex('notes', 'by_folder', folderId) : await d.getAll('notes')
    return rows.sort((a, b) => b.updated_at.localeCompare(a.updated_at))
  },
  async get(id: string): Promise<Note | undefined> {
    return (await db()).get('notes', id)
  },
  /** Áp kết quả sync: note có deleted_at → xoá khỏi cache (tombstone). */
  async apply(changes: Note[]): Promise<void> {
    const tx = (await db()).transaction('notes', 'readwrite')
    for (const n of changes) {
      if (n.deleted_at) await tx.store.delete(n.id)
      else await tx.store.put(n)
    }
    await tx.done
  },
  async remove(ids: string[]): Promise<void> {
    const tx = (await db()).transaction('notes', 'readwrite')
    await Promise.all(ids.map((id) => tx.store.delete(id)))
    await tx.done
  },
  /** Xoá TOÀN BỘ dữ liệu cục bộ (đăng xuất / xoá tài khoản — R-10). */
  async clear(): Promise<void> {
    const d = await db()
    await Promise.all([d.clear('notes'), d.clear('outbox'), d.clear('failed'), d.clear('meta')])
  },
}

export const outbox = {
  async put(item: OutboxItem): Promise<void> {
    await (await db()).put('outbox', item)
  },
  async get(id: string): Promise<OutboxItem | undefined> {
    return (await db()).get('outbox', id)
  },
  async remove(id: string): Promise<boolean> {
    const d = await db()
    const exists = await d.get('outbox', id)
    if (exists) await d.delete('outbox', id)
    return Boolean(exists)
  },
  async due(now = Date.now()): Promise<OutboxItem[]> {
    return (await db()).getAllFromIndex('outbox', 'by_notBefore', IDBKeyRange.upperBound(now))
  },
  async list(): Promise<OutboxItem[]> {
    return (await db()).getAll('outbox')
  },
}

export const failedStore = {
  /** Chuyển mục outbox sang "failed" trong MỘT transaction (không thể mất giữa chừng). */
  async moveFromOutbox(item: OutboxItem, lastError: string): Promise<void> {
    const tx = (await db()).transaction(['outbox', 'failed'], 'readwrite')
    await tx.objectStore('failed').put({ ...item, lastError, failedAt: Date.now() })
    await tx.objectStore('outbox').delete(item.id)
    await tx.done
  },
  /** "Gửi lại": đưa về outbox, gửi ngay, đếm lại số lần thử. */
  async requeue(id: string, now = Date.now()): Promise<boolean> {
    const tx = (await db()).transaction(['outbox', 'failed'], 'readwrite')
    const item = await tx.objectStore('failed').get(id)
    if (item) {
      const { failedAt: _f, ...rest } = item
      await tx.objectStore('outbox').put({ ...rest, attempts: 0, notBefore: now, lastError: undefined })
      await tx.objectStore('failed').delete(id)
    }
    await tx.done
    return Boolean(item)
  },
  async remove(id: string): Promise<void> {
    await (await db()).delete('failed', id)
  },
  async list(): Promise<FailedItem[]> {
    return (await db()).getAll('failed')
  },
}

export const meta = {
  async get(key: string): Promise<string | undefined> {
    return (await (await db()).get('meta', key))?.value
  },
  async set(key: string, value: string): Promise<void> {
    await (await db()).put('meta', { key, value })
  },
}
