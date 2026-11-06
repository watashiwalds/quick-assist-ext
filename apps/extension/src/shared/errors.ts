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
    return { code: this.code, message: this.message, status: this.status, requestId: this.requestId, details: this.details }
  }
}

export interface SerializedError {
  code: string
  message: string
  status: number
  requestId?: string
  details?: Record<string, unknown>
}

/** Thông báo thân thiện cho các mã lỗi phổ biến (UI/UX owner chỉnh ở đây). */
export const USER_MESSAGES: Record<string, string> = {
  NETWORK_ERROR: 'Không kết nối được máy chủ. Ghi chú sẽ được gửi lại khi có mạng.',
  NO_BACKGROUND: 'Tiện ích đang khởi động lại, vui lòng thử lại.',
  NOT_SIGNED_IN: 'Bạn cần đăng nhập để dùng tính năng này.',
  TOKEN_MISSING: 'Bạn cần đăng nhập để dùng tính năng này.',
  TOKEN_EXPIRED: 'Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.',
  TOKEN_INVALID: 'Phiên đăng nhập không hợp lệ, vui lòng đăng nhập lại.',
  REFRESH_REUSED: 'Phiên đăng nhập đã bị thu hồi, vui lòng đăng nhập lại.',
  OAUTH_CANCELLED: 'Bạn đã huỷ đăng nhập.',
  OAUTH_NOT_CONFIGURED: 'Tiện ích chưa được cấu hình đăng nhập Google.',
  OAUTH_UPSTREAM: 'Không kết nối được Google, vui lòng thử lại.',
  QUOTA_EXCEEDED: 'Bạn đã dùng hết hạn mức AI. Xem chi tiết trong Cài đặt.',
  RATE_LIMITED: 'Bạn thao tác quá nhanh, vui lòng thử lại sau ít giây.',
  NOTE_VERSION_CONFLICT: 'Ghi chú đã được sửa ở nơi khác. Tải lại để xem bản mới nhất.',
  NOTE_NOT_FOUND: 'Ghi chú không còn tồn tại.',
  NOTE_TOO_LONG: 'Ghi chú quá dài (tối đa 20 000 ký tự).',
  FOLDER_EXISTS: 'Đã có thư mục cùng tên.',
  FOLDER_IS_DEFAULT: 'Không thể đổi tên hoặc xoá thư mục Inbox.',
  FOLDER_NOT_FOUND: 'Thư mục không còn tồn tại.',
  SUMMARY_INPUT_TOO_LONG: 'Văn bản quá dài để tóm tắt (tối đa 30 000 ký tự).',
  SUMMARY_INPUT_INVALID: 'Không có nội dung để tóm tắt.',
  AI_UNAVAILABLE: 'Dịch vụ AI đang bận, vui lòng thử lại sau.',
  CHAT_INPUT_INVALID: 'Hãy nhập câu hỏi.',
  CHAT_INPUT_TOO_LONG: 'Câu hỏi quá dài (tối đa 2 000 ký tự).',
  NO_SELECTION: 'Hãy bôi đen đoạn văn bản cần ghi chú.',
  VALIDATION_ERROR: 'Dữ liệu không hợp lệ.',
  INTERNAL_ERROR: 'Máy chủ gặp lỗi. Vui lòng thử lại; nếu vẫn lỗi, gửi kèm mã lỗi cho nhóm.',
}

export function userMessage(e: SerializedError): string {
  const base = USER_MESSAGES[e.code] ?? e.message ?? 'Đã có lỗi xảy ra.'
  const wait = e.code === 'RATE_LIMITED' ? Number(e.details?.retry_after) : NaN
  return Number.isFinite(wait) && wait > 0 ? `${base} (chờ ${wait} giây)` : base
}

/** Chuyển lỗi bất kỳ thành SerializedError để hiển thị. */
export function toSerialized(e: unknown): SerializedError {
  if (e instanceof AppError) return e.toJSON()
  return { code: 'UNKNOWN', message: e instanceof Error ? e.message : String(e), status: 0 }
}
