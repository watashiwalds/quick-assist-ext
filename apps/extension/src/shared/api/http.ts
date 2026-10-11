/**
 * HTTP client mức thấp: timeout, request id, map lỗi về AppError.
 * KHÔNG biết gì về token — việc gắn/làm mới token do background/auth đảm nhận
 * (truyền vào qua `getAccessToken` / `onUnauthorized`).
 */
import { config } from '../config'
import { AppError } from '../errors'

export interface HttpOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number | undefined | null>
  headers?: Record<string, string>
  signal?: AbortSignal
}

export interface AuthHooks {
  getAccessToken: () => Promise<string | null>
  /** Gọi khi API trả 401 TOKEN_EXPIRED. Trả true nếu đã refresh thành công → thử lại 1 lần. */
  onUnauthorized: () => Promise<boolean>
}

function buildUrl(path: string, query?: HttpOptions['query']): string {
  const url = new URL(config.apiBaseUrl.replace(/\/$/, '') + path)
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
  }
  return url.toString()
}

async function toAppError(res: Response): Promise<AppError> {
  const rid = res.headers.get('X-Request-ID') ?? undefined
  try {
    const { error } = (await res.json()) as {
      error: { code: string; message: string; details?: Record<string, unknown> }
    }
    return new AppError(error.code, error.message, res.status, rid, error.details)
  } catch {
    return new AppError('HTTP_' + res.status, res.statusText, res.status, rid)
  }
}

export function createHttp(auth?: AuthHooks) {
  async function raw(path: string, opts: HttpOptions, retried: boolean, withTimeout = true): Promise<Response> {
    const headers: Record<string, string> = { Accept: 'application/json', ...opts.headers }
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
    const token = auth ? await auth.getAccessToken() : null
    if (token) headers.Authorization = `Bearer ${token}`

    const signals = [opts.signal, withTimeout ? AbortSignal.timeout(config.requestTimeoutMs) : undefined]
      .filter((s): s is AbortSignal => s !== undefined)
    let res: Response
    try {
      res = await fetch(buildUrl(path, opts.query), {
        method: opts.method ?? 'GET',
        headers,
        body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
        signal: signals.length ? AbortSignal.any(signals) : undefined,
      })
    } catch (e) {
      if (opts.signal?.aborted) throw new AppError('ABORTED', 'Đã huỷ', 0)
      throw new AppError('NETWORK_ERROR', (e as Error).message, 0)
    }
    if (res.status === 401 && auth && !retried) {
      const err = await toAppError(res.clone())
      if (err.code === 'TOKEN_EXPIRED' && (await auth.onUnauthorized())) return raw(path, opts, true, withTimeout)
    }
    return res
  }

  async function request<T>(path: string, opts: HttpOptions = {}): Promise<T> {
    const res = await raw(path, opts, false)
    if (!res.ok) throw await toAppError(res)
    if (res.status === 204) return undefined as T
    return (await res.json()) as T
  }

  /**
   * Gọi endpoint trả luồng (SSE): trả Response để caller tự đọc `body`. Không áp timeout tổng
   * (câu trả lời có thể dài) — caller huỷ bằng `opts.signal` (nút Dừng). Lỗi HTTP vẫn ném AppError.
   */
  async function stream(path: string, opts: HttpOptions = {}): Promise<Response> {
    const res = await raw(path, { ...opts, headers: { Accept: 'text/event-stream', ...opts.headers } }, false, false)
    if (!res.ok) throw await toAppError(res)
    if (!res.body) throw new AppError('NETWORK_ERROR', 'Phản hồi không có nội dung', res.status)
    return res
  }

  return Object.assign(request, { stream })
}

export type HttpRequest = ReturnType<typeof createHttp>
