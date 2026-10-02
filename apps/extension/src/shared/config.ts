/** Cấu hình build-time. Không đặt secret ở đây — mọi thứ trong bundle đều công khai. */
export const config = {
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000/api/v1',
  googleClientId: (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined) ?? '',
  undoWindowMs: 5_000,
  requestTimeoutMs: 15_000,
} as const
