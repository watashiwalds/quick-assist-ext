/**
 * Service worker (MV3) — composition root của extension.
 * Chỉ ĐĂNG KÝ listener; logic nằm trong các file chuyên trách.
 * Mọi listener phải đăng ký đồng bộ ở top-level (yêu cầu của MV3).
 */
import { AppError } from '@/shared/errors'
import { isRpcRequest, type RpcResponse } from '@/shared/messaging/protocol'
import { dispatch } from './handlers'
import { FLUSH_ALARM, flushOutbox, startQuickNote } from './notes/quick-note'
import { getSelection } from './page-actions'

const MENU_QUICK_NOTE = 'qa.quick-note'

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: MENU_QUICK_NOTE, title: 'Ghi chú văn bản này', contexts: ['selection'] })
  chrome.alarms.create(FLUSH_ALARM, { periodInMinutes: 1 })
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => undefined)
})

chrome.runtime.onStartup.addListener(() => void flushOutbox())

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== MENU_QUICK_NOTE || tab?.id === undefined) return
  void startQuickNote(tab.id, { text: info.selectionText ?? '', url: tab.url, title: tab.title })
})

chrome.commands.onCommand.addListener((command, tab) => {
  if (command !== 'quick-note' || tab?.id === undefined) return
  const tabId = tab.id
  void getSelection(tabId).then((sel) => startQuickNote(tabId, sel ?? { text: '' }))
})

chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === FLUSH_ALARM) void flushOutbox()
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
