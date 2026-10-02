/**
 * Lỗi thống nhất phía client — map 1-1 với error contract của API:
 *   { error: { code, message, details, request_id } }
 * UI chỉ dựa vào `code` để chọn thông báo, không parse message.
 */
export class AppError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status = 0,
    readonly requestId?: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message)
    this.name = 'AppError'
  }

  get retryable(): boolean {
    return this.status === 0 || this.status === 429 || this.status >= 500
  }

  toJSON(): SerializedError {
    return { code: this.code, message: this.message, status: this.status, requestId: this.requestId }
  }
}

export interface SerializedError {
  code: string
  message: string
  status: number
  requestId?: string
}

/** Thông báo thân thiện cho các mã lỗi phổ biến (UI/UX owner chỉnh ở đây). */
export const USER_MESSAGES: Record<string, string> = {
  NETWORK_ERROR: 'Không kết nối được máy chủ. Ghi chú sẽ được gửi lại khi có mạng.',
  NOT_SIGNED_IN: 'Bạn cần đăng nhập để dùng tính năng này.',
  TOKEN_EXPIRED: 'Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.',
  REFRESH_REUSED: 'Phiên đăng nhập đã bị thu hồi, vui lòng đăng nhập lại.',
  QUOTA_EXCEEDED: 'Bạn đã dùng hết hạn mức AI.',
  NOTE_VERSION_CONFLICT: 'Ghi chú đã được sửa ở nơi khác. Tải lại để xem bản mới nhất.',
  AI_UNAVAILABLE: 'Dịch vụ AI đang bận, vui lòng thử lại sau.',
  NO_SELECTION: 'Hãy bôi đen đoạn văn bản cần ghi chú.',
}

export function userMessage(e: SerializedError): string {
  return USER_MESSAGES[e.code] ?? e.message ?? 'Đã có lỗi xảy ra.'
}
