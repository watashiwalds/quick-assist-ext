/**
 * Đăng nhập Google: Authorization Code + PKCE qua chrome.identity.launchWebAuthFlow
 * (ADR-0005). Extension chỉ giữ client_id; server đổi code bằng client_secret.
 */
import { createApi } from '@/shared/api/endpoints'
import { createHttp } from '@/shared/api/http'
import { config } from '@/shared/config'
import { AppError } from '@/shared/errors'
import { buildGoogleAuthRequest, parseAuthRedirect } from '@/shared/pkce'
import { saveTokens } from './session'

const publicApi = createApi(createHttp())

export async function loginWithGoogle(): Promise<void> {
  if (!config.googleClientId) throw new AppError('OAUTH_NOT_CONFIGURED', 'Thiếu VITE_GOOGLE_CLIENT_ID')
  const redirectUri = chrome.identity.getRedirectURL() // https://<id>.chromiumapp.org/
  const req = await buildGoogleAuthRequest(config.googleClientId, redirectUri)

  let redirected: string | undefined
  try {
    redirected = await chrome.identity.launchWebAuthFlow({ url: req.url, interactive: true })
  } catch (e) {
    throw new AppError('OAUTH_CANCELLED', (e as Error).message)
  }
  if (!redirected) throw new AppError('OAUTH_CANCELLED', 'Đăng nhập bị huỷ')

  let code: string
  try {
    code = parseAuthRedirect(redirected, req.state)
  } catch (e) {
    throw new AppError((e as Error).message, 'Đăng nhập Google thất bại')
  }
  const tokens = await publicApi.auth.exchangeGoogle({
    code,
    code_verifier: req.verifier,
    redirect_uri: redirectUri,
    nonce: req.nonce,
  })
  await saveTokens(tokens)
}
