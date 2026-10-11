/** Phía GỌI RPC — dùng trong UI (popup/sidepanel). */
import { AppError } from '../errors'
import type { BroadcastEvent, ChatClientMessage, ChatPortEvent, RpcReq, RpcRequest, RpcRes, RpcResponse, RpcType } from './protocol'
import { CHAT_PORT, isBroadcast } from './protocol'

export async function rpc<K extends RpcType>(type: K, ...args: RpcReq<K> extends void ? [] : [RpcReq<K>]) {
  const msg: RpcRequest<K> = { channel: 'qa-rpc', type, payload: args[0] as RpcReq<K> }
  const res = (await chrome.runtime.sendMessage(msg)) as RpcResponse<RpcRes<K>> | undefined
  if (!res) throw new AppError('NO_BACKGROUND', 'Background không phản hồi')
  if (!res.ok) {
    throw new AppError(res.error.code, res.error.message, res.error.status, res.error.requestId, res.error.details)
  }
  return res.data
}

export function onBroadcast(handler: (e: BroadcastEvent) => void): () => void {
  const listener = (m: unknown) => {
    if (isBroadcast(m)) handler(m)
  }
  chrome.runtime.onMessage.addListener(listener)
  return () => chrome.runtime.onMessage.removeListener(listener)
}

/**
 * Hỏi chat RAG: mở Port riêng cho câu hỏi này, nhận từng sự kiện qua `onEvent`.
 * Luôn kết thúc bằng đúng MỘT sự kiện cuối: done | stopped | error. Trả hàm `stop()`.
 */
export function askChat(
  req: Omit<Extract<ChatClientMessage, { type: 'ask' }>, 'type'>,
  onEvent: (e: ChatPortEvent) => void,
): { stop: () => void } {
  const port = chrome.runtime.connect({ name: CHAT_PORT })
  let finished = false
  const finish = (e: ChatPortEvent) => {
    if (finished) return
    finished = true
    onEvent(e)
    try {
      port.disconnect()
    } catch {
      /* đã đóng */
    }
  }
  port.onMessage.addListener((e: ChatPortEvent) => {
    if (e.type === 'done' || e.type === 'stopped' || e.type === 'error') finish(e)
    else if (!finished) onEvent(e)
  })
  port.onDisconnect.addListener(() =>
    finish({ type: 'error', error: new AppError('NO_BACKGROUND', 'Mất kết nối với tiện ích').toJSON() }),
  )
  port.postMessage({ type: 'ask', ...req } satisfies ChatClientMessage)
  return {
    stop() {
      if (finished) return
      try {
        port.postMessage({ type: 'stop' } satisfies ChatClientMessage)
      } catch {
        finish({ type: 'stopped' })
      }
    },
  }
}
