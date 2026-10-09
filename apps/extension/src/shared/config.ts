/** Cấu hình build-time. Không đặt secret ở đây — mọi thứ trong bundle đều công khai. */
export const config = {
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000/api/v1',
  googleClientId: (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined) ?? '',
  undoWindowMs: 5_000,
  requestTimeoutMs: 15_000,
  /** = MAX_NOTE_CHARS của backend (P02): vùng chọn dài hơn bị cắt và báo người dùng. */
  maxNoteChars: 20_000,
  /** = MAX_SUMMARY_INPUT_CHARS của backend (SUM-01). */
  maxSummaryChars: 30_000,
  /** Bản build E2E (VITE_E2E=true) mới có đăng nhập thử & hook kiểm thử — bản phát hành KHÔNG có. */
  e2e: import.meta.env.VITE_E2E === 'true',
} as const
