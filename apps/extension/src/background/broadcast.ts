import type { BroadcastEvent } from '@/shared/messaging/protocol'

/** Gửi sự kiện tới mọi UI đang mở. Không có UI nào mở → bỏ qua lỗi "no receiver". */
export function broadcast(e: BroadcastEvent): void {
  chrome.runtime.sendMessage(e).catch(() => undefined)
}
