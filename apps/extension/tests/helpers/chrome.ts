/** Giả lập tối thiểu API chrome.* cho unit test background/UI (không cần trình duyệt). */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { vi } from 'vitest'

function area() {
  let data: Record<string, unknown> = {}
  return {
    get: vi.fn(async (key?: string | string[]) => {
      if (key === undefined) return { ...data }
      const keys = Array.isArray(key) ? key : [key]
      return Object.fromEntries(keys.filter((k) => k in data).map((k) => [k, data[k]]))
    }),
    set: vi.fn(async (items: Record<string, unknown>) => {
      data = { ...data, ...structuredClone(items) }
    }),
    remove: vi.fn(async (key: string | string[]) => {
      for (const k of Array.isArray(key) ? key : [key]) delete data[k]
    }),
    clear: vi.fn(async () => {
      data = {}
    }),
    _dump: () => data,
  }
}

export function installChrome() {
  const sent: unknown[] = []
  const chromeFake = {
    runtime: {
      id: 'test-ext',
      sendMessage: vi.fn(async (m: unknown): Promise<any> => {
        sent.push(m)
        return undefined
      }),
      onMessage: { addListener: vi.fn(), removeListener: vi.fn() },
      getURL: (p: string) => `chrome-extension://test-ext/${p}`,
    },
    storage: { local: area(), session: area() },
    scripting: { executeScript: vi.fn(async (_opts: any): Promise<any> => [{ result: undefined }]) },
    contextMenus: { create: vi.fn(), removeAll: vi.fn(async () => undefined) },
    identity: { getRedirectURL: () => 'https://test-ext.chromiumapp.org/', launchWebAuthFlow: vi.fn() },
  }
  ;(globalThis as Record<string, unknown>).chrome = chromeFake
  return { chrome: chromeFake, sent }
}
