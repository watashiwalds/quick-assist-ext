/** Instance API có xác thực — chỉ dùng trong background. */
import { createApi } from '@/shared/api/endpoints'
import { createHttp } from '@/shared/api/http'
import { getAccessToken, refreshSession } from './auth/session'

export const http = createHttp({ getAccessToken, onUnauthorized: refreshSession })
export const api = createApi(http)
