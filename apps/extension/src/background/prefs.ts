/** Tuỳ chọn người dùng lưu cục bộ (chrome.storage.local) — xoá khi đăng xuất/xoá tài khoản. */
import type { Preferences } from '@/shared/messaging/protocol'

const KEY = 'qa.prefs'
const DEFAULTS: Preferences = { defaultFolderId: null }

export async function getPrefs(): Promise<Preferences> {
  const v = (await chrome.storage.local.get(KEY))[KEY] as Partial<Preferences> | undefined
  return { ...DEFAULTS, ...v }
}

export async function setPrefs(patch: Partial<Preferences>): Promise<Preferences> {
  const next = { ...(await getPrefs()), ...patch }
  await chrome.storage.local.set({ [KEY]: next })
  return next
}

export async function clearPrefs(): Promise<void> {
  await chrome.storage.local.remove(KEY)
}
