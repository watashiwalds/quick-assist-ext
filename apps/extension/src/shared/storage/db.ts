/**
 * IndexedDB local (ADR-0008):
 *  - notes   : cache đọc (stale-while-revalidate) — nguồn sự thật vẫn là server.
 *  - outbox  : hàng đợi ghi chú chưa gửi được (mất mạng / đang trong 5s hoàn tác).
 *  - meta    : con trỏ đồng bộ (lastSyncAt).
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

interface QADB extends DBSchema {
  notes: { key: string; value: Note; indexes: { by_folder: string; by_updated: string } }
  outbox: { key: string; value: OutboxItem; indexes: { by_notBefore: number } }
  meta: { key: string; value: { key: string; value: string } }
}

let dbp: Promise<IDBPDatabase<QADB>> | null = null

export function db(): Promise<IDBPDatabase<QADB>> {
  dbp ??= openDB<QADB>('quickassist', 1, {
    upgrade(d) {
      const notes = d.createObjectStore('notes', { keyPath: 'id' })
      notes.createIndex('by_folder', 'folder_id')
      notes.createIndex('by_updated', 'updated_at')
      d.createObjectStore('outbox', { keyPath: 'id' }).createIndex('by_notBefore', 'notBefore')
      d.createObjectStore('meta', { keyPath: 'key' })
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
  async clear(): Promise<void> {
    const d = await db()
    await Promise.all([d.clear('notes'), d.clear('outbox'), d.clear('meta')])
  },
}

export const outbox = {
  async put(item: OutboxItem): Promise<void> {
    await (await db()).put('outbox', item)
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
}

export const meta = {
  async get(key: string): Promise<string | undefined> {
    return (await (await db()).get('meta', key))?.value
  },
  async set(key: string, value: string): Promise<void> {
    await (await db()).put('meta', { key, value })
  },
}
