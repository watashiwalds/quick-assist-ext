/** Phía GỌI RPC — dùng trong UI (popup/sidepanel). */
import { AppError } from '../errors'
import type { BroadcastEvent, RpcReq, RpcRequest, RpcRes, RpcResponse, RpcType } from './protocol'
import { isBroadcast } from './protocol'

export async function rpc<K extends RpcType>(type: K, ...args: RpcReq<K> extends void ? [] : [RpcReq<K>]) {
  const msg: RpcRequest<K> = { channel: 'qa-rpc', type, payload: args[0] as RpcReq<K> }
  const res = (await chrome.runtime.sendMessage(msg)) as RpcResponse<RpcRes<K>> | undefined
  if (!res) throw new AppError('NO_BACKGROUND', 'Background không phản hồi')
  if (!res.ok) throw new AppError(res.error.code, res.error.message, res.error.status, res.error.requestId)
  return res.data
}

export function onBroadcast(handler: (e: BroadcastEvent) => void): () => void {
  const listener = (m: unknown) => {
    if (isBroadcast(m)) handler(m)
  }
  chrome.runtime.onMessage.addListener(listener)
  return () => chrome.runtime.onMessage.removeListener(listener)
}
