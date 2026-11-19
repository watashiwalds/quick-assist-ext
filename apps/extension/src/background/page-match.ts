/**
 * AutoChunk — "Tìm trong trang" (ADR-0013, ADR-0015): chụp HTML tab đang xem (hoặc nhận nội dung người
 * dùng dán) → POST /ai/page-match/stream (SSE) → kết quả cho side panel; click đoạn → tìm lại + làm nổi
 * bật trên trang. Background là gateway duy nhất (ADR-0007).
 *
 * Phase 3: server phát tiến độ từng lô embed; mỗi lần quét giữ một AbortController theo `requestId` để UI
 * huỷ giữa chừng. Uỷ quyền quota do server lo (một lease, release khi kết nối đóng).
 */
import { config } from '@/shared/config'
import {
  getPageTextChars,
  getRawHtml,
  type HighlightResult,
  type HighlightTarget,
  highlightBlocksByText,
  type RawPage,
} from '@/content/injected'
import { AppError } from '@/shared/errors'
import { createSseParser } from '@/shared/api/sse'
import type { PageMatchRequest, PageMatchResult } from '@/shared/api/types'
import type { PageMatchRun } from '@/shared/messaging/protocol'
import { api } from './api'
import { broadcast } from './broadcast'

const RUNNING = new Map<string, AbortController>()

async function activeTab(): Promise<chrome.tabs.Tab> {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
  if (tab?.id === undefined) throw new AppError('NO_ACTIVE_TAB', 'Không tìm thấy tab đang mở')
  return tab
}

async function capture(tabId: number): Promise<RawPage> {
  try {
    const [res] = await chrome.scripting.executeScript({ target: { tabId }, func: getRawHtml, args: [config.pageMatchMaxHtmlBytes] })
    const page = res?.result as RawPage | undefined
    if (!page) throw new Error('empty result')
    return page
  } catch {
    // chrome://, Web Store, PDF viewer… hoặc chưa có quyền đọc trang (activeTab hết hạn sau khi chuyển trang).
    throw new AppError('PAGE_ACCESS_DENIED', 'Không đọc được nội dung trang này', 0)
  }
}

/** Ước lượng độ dài văn bản TRƯỚC khi quét — UI hỏi người dùng 50k/toàn bộ nếu vượt ngưỡng. */
export async function inspectPage(): Promise<{ textChars: number; url: string; title: string }> {
  const tab = await activeTab()
  const tabId = tab.id as number
  try {
    const [res] = await chrome.scripting.executeScript({ target: { tabId }, func: getPageTextChars })
    const textChars = res?.result as number | undefined
    if (typeof textChars !== 'number') throw new Error('empty result')
    return { textChars, url: tab.url ?? '', title: tab.title ?? '' }
  } catch {
    throw new AppError('PAGE_ACCESS_DENIED', 'Không đọc được nội dung trang này', 0)
  }
}

/** Huỷ lần quét đang chạy: abort fetch → server thấy client đóng và release quota giữ chỗ. */
export function cancelPageMatch(requestId: string): void {
  RUNNING.get(requestId)?.abort()
}

interface RunArgs {
  query: string
  text?: string
  scanAll?: boolean
  requestId?: string
}

async function streamMatch(body: PageMatchRequest, requestId?: string): Promise<PageMatchResult> {
  const ctrl = new AbortController()
  if (requestId) RUNNING.set(requestId, ctrl)
  const out: { result?: PageMatchResult; error?: AppError } = {}
  const parser = createSseParser(({ event, data }) => {
    try {
      const d = JSON.parse(data) as Record<string, unknown>
      if (event === 'progress') {
        const phase = d.phase as 'extract' | 'batch' | 'verify'
        broadcast({
          channel: 'qa-event',
          type: 'pageMatch/progress',
          phase,
          ...(typeof d.index === 'number' ? { index: d.index } : {}),
          ...(typeof d.total === 'number' ? { total: d.total } : {}),
        })
      } else if (event === 'done') {
        out.result = d as unknown as PageMatchResult
      } else if (event === 'error') {
        out.error = new AppError(
          String(d.code ?? 'AI_UNAVAILABLE'),
          String(d.message ?? 'Không quét được trang lúc này'),
          Number(d.status ?? 502),
        )
      }
    } catch {
      /* sự kiện hỏng → bỏ qua; kết thúc luồng sẽ báo lỗi mạng nếu chưa có done */
    }
  })
  try {
    const res = await api.ai.pageMatchStream(body, ctrl.signal)
    const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader()
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      parser.feed(value)
    }
    parser.end()
  } catch (e) {
    if (ctrl.signal.aborted) throw new AppError('ABORTED', 'Đã huỷ lần quét', 0)
    if (e instanceof AppError) throw e
    throw new AppError('NETWORK_ERROR', String(e), 0)
  } finally {
    if (requestId) RUNNING.delete(requestId)
  }
  if (out.error) throw out.error
  if (!out.result) throw new AppError('NETWORK_ERROR', 'Mất kết nối giữa chừng', 0)
  return out.result
}

export async function runPageMatch({ query, text, scanAll = false, requestId }: RunArgs): Promise<PageMatchRun> {
  if (text !== undefined) {
    // Nguồn dán: không cần tab/quyền đọc trang; tiến độ nhảy thẳng sang bước trích/embed.
    if (!text.trim()) throw new AppError('PAGE_NO_CONTENT', 'Nội dung dán đang trống', 422)
    const result = await streamMatch({ query, text, url: null, scan_all: scanAll }, requestId)
    return { ...result, url: null, title: null }
  }

  const tab = await activeTab()
  const page = await capture(tab.id as number)
  if (page.tooLong) {
    throw new AppError('PAGE_TOO_LONG', 'Trang quá dài để quét', 413, undefined, { bytes: page.bytes })
  }
  if (!/^https?:/.test(page.url)) throw new AppError('PAGE_ACCESS_DENIED', 'Không quét được trang này', 0)
  const result = await streamMatch({
    query,
    html: page.html,
    url: page.url,
    title: page.title.slice(0, 500) || null,
    scan_all: scanAll,
  }, requestId)
  return { ...result, tabId: tab.id, url: page.url, title: page.title || null }
}

export async function highlightInTab(tabId: number, items: HighlightTarget[]): Promise<HighlightResult> {
  try {
    const [res] = await chrome.scripting.executeScript({ target: { tabId }, func: highlightBlocksByText, args: [items] })
    return (res?.result as HighlightResult | undefined) ?? { ok: false, found: 0, total: items.length }
  } catch {
    return { ok: false, found: 0, total: items.length } // tab đã đóng / điều hướng sang trang không cho tiêm
  }
}
