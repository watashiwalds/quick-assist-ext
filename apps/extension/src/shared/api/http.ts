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
  async function raw(path: string, opts: HttpOptions, retried: boolean): Promise<Response> {
    const headers: Record<string, string> = { Accept: 'application/json', ...opts.headers }
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
    const token = auth ? await auth.getAccessToken() : null
    if (token) headers.Authorization = `Bearer ${token}`

    const timeout = AbortSignal.timeout(config.requestTimeoutMs)
    let res: Response
    try {
      res = await fetch(buildUrl(path, opts.query), {
        method: opts.method ?? 'GET',
        headers,
        body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
        signal: opts.signal ? AbortSignal.any([opts.signal, timeout]) : timeout,
      })
    } catch (e) {
      throw new AppError('NETWORK_ERROR', (e as Error).message, 0)
    }
    if (res.status === 401 && auth && !retried) {
      const err = await toAppError(res.clone())
      if (err.code === 'TOKEN_EXPIRED' && (await auth.onUnauthorized())) return raw(path, opts, true)
    }
    return res
  }

  return async function request<T>(path: string, opts: HttpOptions = {}): Promise<T> {
    const res = await raw(path, opts, false)
    if (!res.ok) throw await toAppError(res)
    if (res.status === 204) return undefined as T
    return (await res.json()) as T
  }
}

export type HttpRequest = ReturnType<typeof createHttp>
