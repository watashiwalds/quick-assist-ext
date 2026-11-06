/**
 * Service worker (MV3) — composition root của extension.
 * Chỉ ĐĂNG KÝ listener; logic nằm trong các file chuyên trách.
 * Mọi listener phải đăng ký đồng bộ ở top-level (yêu cầu của MV3).
 */
import { AppError } from '@/shared/errors'
import { CHAT_PORT, isRpcRequest, type RpcResponse } from '@/shared/messaging/protocol'
import { broadcast } from './broadcast'
import { handleChatPort } from './chat'
import { dispatch } from './handlers'
import { folderIdFromMenu, MENU_QUICK_NOTE, MENU_SUMMARIZE, rebuildMenus } from './menus'
import { FLUSH_ALARM, flushOutbox, startQuickNote } from './notes/quick-note'
import { getSelection } from './page-actions'
import { setPendingSelection } from './selection'

chrome.runtime.onInstalled.addListener(() => {
  void rebuildMenus()
  chrome.alarms.create(FLUSH_ALARM, { periodInMinutes: 1 })
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => undefined)
})

chrome.runtime.onStartup.addListener(() => {
  void rebuildMenus()
  void flushOutbox()
})

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (tab?.id === undefined) return
  const sel = { text: info.selectionText ?? '', url: tab.url, title: tab.title }
  if (info.menuItemId === MENU_SUMMARIZE) {
    // sidePanel.open phải gọi ĐỒNG BỘ trong user gesture → mở trước, lưu vùng chọn sau.
    chrome.sidePanel.open({ tabId: tab.id }).catch(() => undefined)
    void setPendingSelection(sel).then(() => broadcast({ channel: 'qa-event', type: 'selection/pending' }))
    return
  }
  if (info.menuItemId === MENU_QUICK_NOTE) {
    void startQuickNote(tab.id, sel)
    return
  }
  const folderId = folderIdFromMenu(info.menuItemId)
  if (folderId) void startQuickNote(tab.id, sel, folderId)
})

chrome.commands.onCommand.addListener((command, tab) => {
  if (command !== 'quick-note' || tab?.id === undefined) return
  const tabId = tab.id
  void getSelection(tabId).then((sel) => startQuickNote(tabId, sel ?? { text: '' }))
})

chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === FLUSH_ALARM) void flushOutbox()
})

// Chat RAG: mỗi câu hỏi một Port (stream từng phần câu trả lời) — background/chat.ts
chrome.runtime.onConnect.addListener((port) => {
  if (port.name === CHAT_PORT && port.sender?.id === chrome.runtime.id) handleChatPort(port)
})

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!isRpcRequest(msg) || sender.id !== chrome.runtime.id) return false
  dispatch(msg.type, msg.payload as never)
    .then((data) => sendResponse({ ok: true, data } satisfies RpcResponse<unknown>))
    .catch((e: unknown) => {
      const err = e instanceof AppError ? e : new AppError('UNKNOWN', String(e))
      sendResponse({ ok: false, error: err.toJSON() } satisfies RpcResponse<unknown>)
    })
  return true // giữ kênh mở cho sendResponse bất đồng bộ
})

// Hook kiểm thử E2E (N07): Playwright gọi qua service worker. Vite thay import.meta.env.VITE_E2E lúc build
// → bản phát hành loại bỏ hẳn khối này khỏi bundle (kiểm tra bởi scripts/check-bundle.mjs — H01).
if (import.meta.env.VITE_E2E === 'true') {
  ;(globalThis as Record<string, unknown>).__qaE2E = { startQuickNote, flushOutbox, rebuildMenus, dispatch, getSelection, setPendingSelection }
}
