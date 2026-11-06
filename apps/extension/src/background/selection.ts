/** Vùng chọn chờ tóm tắt (SUM-03): menu chuột phải → lưu tạm → side panel lấy ra hiển thị. */
import { config } from '@/shared/config'
import type { PendingSelection } from '@/shared/messaging/protocol'

const KEY = 'qa.pendingSelection'

export async function setPendingSelection(sel: { text: string; url?: string; title?: string }): Promise<PendingSelection> {
  const text = sel.text.trim()
  const pending: PendingSelection = {
    text: text.slice(0, config.maxSummaryChars),
    url: sel.url?.startsWith('http') ? sel.url : null,
    title: sel.title?.slice(0, 500) ?? null,
    truncated: text.length > config.maxSummaryChars,
    at: Date.now(),
  }
  // storage.session: chỉ trong phiên trình duyệt, không đồng bộ, không ghi đĩa lâu dài.
  await chrome.storage.session.set({ [KEY]: pending })
  return pending
}

export async function takePendingSelection(): Promise<PendingSelection | null> {
  const v = (await chrome.storage.session.get(KEY))[KEY] as PendingSelection | undefined
  if (!v) return null
  await chrome.storage.session.remove(KEY)
  return Date.now() - v.at < 10 * 60_000 ? v : null // quá 10 phút → bỏ
}
