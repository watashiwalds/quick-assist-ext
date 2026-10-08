/** Fixture E2E: Chromium + extension bản E2E, đăng nhập thử (dev-login), client API, truy cập DB. */
import { type BrowserContext, chromium, test as base, type Page, type Worker } from '@playwright/test'
import { join } from 'node:path'
import pg from 'pg'

export const API = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000/api/v1'
export const PAGE = 'http://127.0.0.1:4173/article.html'
const DB = process.env.E2E_DATABASE_URL ?? 'postgres://postgres:postgres@localhost:5432/quickassist'
const DIST = join(import.meta.dirname, '..', 'dist-e2e')

export interface ApiClient {
  token: string
  get<T = any>(path: string): Promise<T>
  send<T = any>(method: string, path: string, body?: unknown, headers?: Record<string, string>): Promise<{ status: number; body: T }>
  notes(): Promise<any[]>
  waitForNote(pred: (n: any) => boolean, timeoutMs?: number): Promise<any>
}

async function apiFor(email: string): Promise<ApiClient> {
  const r = await fetch(`${API}/auth/dev-login`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email }) })
  if (!r.ok) throw new Error(`dev-login ${r.status} — backend cần ENABLE_DEV_LOGIN=true`)
  const token = ((await r.json()) as { access_token: string }).access_token
  const send = async (method: string, path: string, body?: unknown, headers: Record<string, string> = {}) => {
    const res = await fetch(API + path, {
      method,
      headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json', ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    return { status: res.status, body: res.status === 204 ? (undefined as any) : await res.json() }
  }
  const client: ApiClient = {
    token,
    get: async (p) => (await send('GET', p)).body,
    send,
    notes: async () => (await send('GET', '/notes?limit=200')).body.items,
    waitForNote: async (pred, timeoutMs = 20_000) => {
      const end = Date.now() + timeoutMs
      for (;;) {
        const n = (await client.notes()).find(pred)
        if (n || Date.now() > end) return n
        await new Promise((r) => setTimeout(r, 500))
      }
    },
  }
  return client
}

export async function sql(query: string, params: unknown[] = []) {
  const c = new pg.Client({ connectionString: DB })
  await c.connect()
  try {
    return (await c.query(query, params)).rows
  } finally {
    await c.end()
  }
}

type Fixtures = { context: BrowserContext; sw: Worker; extId: string; email: string; api: ApiClient; panel: Page }

export const test = base.extend<Fixtures>({
  // eslint-disable-next-line no-empty-pattern
  context: async ({}, use) => {
    const ctx = await chromium.launchPersistentContext('', {
      channel: 'chromium', // headless "mới" hỗ trợ extension
      headless: process.env.E2E_HEADED !== '1',
      args: [`--disable-extensions-except=${DIST}`, `--load-extension=${DIST}`],
    })
    await use(ctx)
    await ctx.close()
  },
  sw: async ({ context }, use) => {
    const sw = context.serviceWorkers()[0] ?? (await context.waitForEvent('serviceworker'))
    await use(sw)
  },
  extId: async ({ sw }, use) => use(new URL(sw.url()).host),
  // eslint-disable-next-line no-empty-pattern
  email: async ({}, use, info) => use(`e2e-${info.title.slice(0, 20).replace(/\W+/g, '-')}-${Date.now()}@test.local`.toLowerCase()),
  api: async ({ email }, use) => use(await apiFor(email)),
  panel: async ({ context, extId, email, api: _api }, use) => {
    const page = await context.newPage()
    await page.goto(`chrome-extension://${extId}/src/ui/sidepanel/index.html`)
    const res = await page.evaluate(
      (e) => chrome.runtime.sendMessage({ channel: 'qa-rpc', type: 'e2e/devLogin', payload: { email: e } }),
      email,
    )
    if (!res?.ok) throw new Error(`devLogin: ${JSON.stringify(res)}`)
    await page.reload()
    await page.getByRole('tab', { name: 'Thư viện' }).waitFor()
    await use(page)
  },
})

export { expect } from '@playwright/test'

/** Mở trang bài viết, bôi đen đoạn #id, trả tabId (tra trong service worker). */
export async function openArticleAndSelect(context: BrowserContext, sw: Worker, selector = '#p1'): Promise<{ page: Page; tabId: number; text: string }> {
  const page = await context.newPage()
  await page.goto(PAGE)
  const text = await page.evaluate((sel) => {
    const el = document.querySelector(sel)!
    const r = document.createRange()
    r.selectNodeContents(el)
    getSelection()!.removeAllRanges()
    getSelection()!.addRange(r)
    return getSelection()!.toString()
  }, selector)
  await page.bringToFront()
  const tabId = await sw.evaluate(async (url) => (await chrome.tabs.query({ url }))[0]!.id!, PAGE)
  return { page, tabId, text }
}

/** Giống phím tắt Alt+Shift+N: đọc vùng chọn qua chrome.scripting rồi lưu nhanh. */
export function quickNoteViaShortcut(sw: Worker, tabId: number, folderId?: string) {
  return sw.evaluate(
    async ([t, f]) => {
      const qa = (globalThis as any).__qaE2E
      const sel = await qa.getSelection(t)
      return qa.startQuickNote(t, sel ?? { text: '' }, f ?? undefined)
    },
    [tabId, folderId ?? null] as const,
  )
}

export async function flushNow(sw: Worker) {
  await sw.evaluate(async () => {
    const d = await new Promise<IDBDatabase>((ok, err) => {
      const r = indexedDB.open('quickassist')
      r.onsuccess = () => ok(r.result)
      r.onerror = () => err(r.error)
    })
    const tx = d.transaction('outbox', 'readwrite')
    const store = tx.objectStore('outbox')
    await new Promise<void>((ok) => {
      const req = store.getAll()
      req.onsuccess = () => {
        for (const item of req.result) store.put({ ...item, notBefore: 0 })
        ok()
      }
    })
    await new Promise((ok) => (tx.oncomplete = ok))
    await (globalThis as any).__qaE2E.flushOutbox()
  })
}
