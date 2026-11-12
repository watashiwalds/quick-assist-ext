/**
 * AutoChunk — "Tìm trong trang" (ADR-0013, ADR-0015): chụp HTML tab đang xem (hoặc nhận nội dung người
 * dùng dán) → POST /ai/page-match → kết quả cho side panel; click đoạn → tìm lại + làm nổi bật trên trang.
 * Background là gateway duy nhất (ADR-0007).
 */
import { config } from '@/shared/config'
import { getRawHtml, type HighlightResult, type HighlightTarget, highlightBlocksByText, type RawPage } from '@/content/injected'
import { AppError } from '@/shared/errors'
import type { PageMatchRun } from '@/shared/messaging/protocol'
import { api } from './api'
import { broadcast } from './broadcast'

async function activeTabId(): Promise<number> {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
  if (tab?.id === undefined) throw new AppError('NO_ACTIVE_TAB', 'Không tìm thấy tab đang mở')
  return tab.id
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

export async function runPageMatch({ query, text }: { query: string; text?: string }): Promise<PageMatchRun> {
  if (text !== undefined) {
    // Nguồn dán: không cần tab/quyền đọc trang; tiến độ nhảy thẳng sang bước phân tích.
    if (!text.trim()) throw new AppError('PAGE_NO_CONTENT', 'Nội dung dán đang trống', 422)
    broadcast({ channel: 'qa-event', type: 'pageMatch/progress', phase: 'analyzing' })
    const result = await api.ai.pageMatch({ query, text, url: null })
    return { ...result, url: null, title: null }
  }

  const tabId = await activeTabId()
  const page = await capture(tabId)
  if (page.tooLong) {
    throw new AppError('PAGE_TOO_LONG', 'Trang quá dài để quét', 413, undefined, { bytes: page.bytes })
  }
  if (!/^https?:/.test(page.url)) throw new AppError('PAGE_ACCESS_DENIED', 'Không quét được trang này', 0)
  broadcast({ channel: 'qa-event', type: 'pageMatch/progress', phase: 'analyzing' })
  const result = await api.ai.pageMatch({ query, html: page.html, url: page.url, title: page.title.slice(0, 500) || null })
  return { ...result, tabId, url: page.url, title: page.title || null }
}

export async function highlightInTab(tabId: number, items: HighlightTarget[]): Promise<HighlightResult> {
  try {
    const [res] = await chrome.scripting.executeScript({ target: { tabId }, func: highlightBlocksByText, args: [items] })
    return (res?.result as HighlightResult | undefined) ?? { ok: false, found: 0, total: items.length }
  } catch {
    return { ok: false, found: 0, total: items.length } // tab đã đóng / điều hướng sang trang không cho tiêm
  }
}
