/**
 * Lưu và làm mới app session.
 *  - access token  → chrome.storage.session (mất khi đóng trình duyệt, không đồng bộ)
 *  - refresh token → chrome.storage.local  (giữ đăng nhập qua lần mở sau)
 * Không bao giờ log token (SDS §8).
 */
import { createApi } from '@/shared/api/endpoints'
import { createHttp } from '@/shared/api/http'
import type { TokenPair } from '@/shared/api/types'

const ACCESS = 'qa.access'
const REFRESH = 'qa.refresh'

// Client KHÔNG gắn token — chỉ dùng cho /auth/refresh và /auth/logout.
const publicApi = createApi(createHttp())

export async function saveTokens(t: TokenPair): Promise<void> {
  const expiresAt = Date.now() + t.expires_in * 1000
  await chrome.storage.session.set({ [ACCESS]: { token: t.access_token, expiresAt } })
  await chrome.storage.local.set({ [REFRESH]: t.refresh_token })
}

export async function clearTokens(): Promise<void> {
  await chrome.storage.session.remove(ACCESS)
  await chrome.storage.local.remove(REFRESH)
}

export async function hasSession(): Promise<boolean> {
  return Boolean((await chrome.storage.local.get(REFRESH))[REFRESH])
}

let refreshing: Promise<boolean> | null = null

/** Single-flight: nhiều request cùng gặp 401 chỉ gọi refresh MỘT lần (tránh REFRESH_REUSED). */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    const rt = (await chrome.storage.local.get(REFRESH))[REFRESH] as string | undefined
    if (!rt) return false
    try {
      await saveTokens(await publicApi.auth.refresh(rt))
      return true
    } catch {
      await clearTokens()
      return false
    }
  })().finally(() => {
    refreshing = null
  })
  return refreshing
}

export async function getAccessToken(): Promise<string | null> {
  const a = (await chrome.storage.session.get(ACCESS))[ACCESS] as
    | { token: string; expiresAt: number }
    | undefined
  if (a && a.expiresAt - 30_000 > Date.now()) return a.token
  return (await refreshSession()) ? getAccessToken() : null
}

export async function logoutRemote(): Promise<void> {
  const rt = (await chrome.storage.local.get(REFRESH))[REFRESH] as string | undefined
  if (rt) await publicApi.auth.logout(rt).catch(() => undefined)
  await clearTokens()
}
