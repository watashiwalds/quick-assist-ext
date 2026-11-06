/**
 * Menu chuột phải (N01, C04, SUM-03). Chrome tự gom các mục của extension vào "QuickAssist ▸".
 *  - "Ghi chú văn bản này"           → thư mục mặc định (Cài đặt), mặc định Inbox
 *  - "Ghi chú vào thư mục ▸ <tên>"   → chọn thư mục khi lưu nhanh (C04)
 *  - "Tóm tắt đoạn văn bản này"      → mở side panel với bản xem trước (SUM-03)
 * Danh sách thư mục lấy từ cache (meta 'folders') → dựng được cả khi offline.
 */
import type { Folder } from '@/shared/api/types'
import { meta } from '@/shared/storage/db'

export const MENU_QUICK_NOTE = 'qa.quick-note'
export const MENU_SUMMARIZE = 'qa.summarize'
const MENU_FOLDERS = 'qa.folders'
const FOLDER_PREFIX = 'qa.folder:'
const MAX_FOLDERS_IN_MENU = 15
const FOLDERS_KEY = 'folders'

export function folderIdFromMenu(menuItemId: string | number): string | null {
  const id = String(menuItemId)
  return id.startsWith(FOLDER_PREFIX) ? id.slice(FOLDER_PREFIX.length) : null
}

export async function cachedFolders(): Promise<Pick<Folder, 'id' | 'name' | 'is_default'>[]> {
  try {
    return JSON.parse((await meta.get(FOLDERS_KEY)) ?? '[]')
  } catch {
    return []
  }
}

export async function rememberFolders(folders: Folder[]): Promise<void> {
  await meta.set(FOLDERS_KEY, JSON.stringify(folders.map(({ id, name, is_default }) => ({ id, name, is_default }))))
  await rebuildMenus()
}

let building: Promise<void> | null = null

export function rebuildMenus(): Promise<void> {
  // Tuần tự hoá: removeAll + create song song sẽ báo "duplicate id".
  const run = async () => {
    await chrome.contextMenus.removeAll()
    const ctx: ['selection'] = ['selection']
    chrome.contextMenus.create({ id: MENU_QUICK_NOTE, title: 'Ghi chú văn bản này', contexts: ctx })
    const folders = await cachedFolders()
    if (folders.length > 0) {
      chrome.contextMenus.create({ id: MENU_FOLDERS, title: 'Ghi chú vào thư mục', contexts: ctx })
      for (const f of folders.slice(0, MAX_FOLDERS_IN_MENU)) {
        chrome.contextMenus.create({ id: FOLDER_PREFIX + f.id, parentId: MENU_FOLDERS, title: f.name, contexts: ctx })
      }
    }
    chrome.contextMenus.create({ id: MENU_SUMMARIZE, title: 'Tóm tắt đoạn văn bản này', contexts: ctx })
  }
  building = (building ?? Promise.resolve()).then(run, run)
  return building
}
