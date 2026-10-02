/** PKCE (RFC 7636) + state/nonce — hàm thuần, unit test được. */

function base64url(bytes: Uint8Array): string {
  let s = ''
  for (const b of bytes) s += String.fromCharCode(b)
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export function randomString(byteLength = 32): string {
  return base64url(crypto.getRandomValues(new Uint8Array(byteLength)))
}

export async function pkceChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  return base64url(new Uint8Array(digest))
}

export interface AuthRequest {
  url: string
  state: string
  nonce: string
  verifier: string
}

export async function buildGoogleAuthRequest(clientId: string, redirectUri: string): Promise<AuthRequest> {
  const verifier = randomString(48) // 64 ký tự, nằm trong [43,128]
  const state = randomString(16)
  const nonce = randomString(16)
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'openid email profile',
    code_challenge: await pkceChallenge(verifier),
    code_challenge_method: 'S256',
    state,
    nonce,
    prompt: 'select_account',
  })
  return { url: `https://accounts.google.com/o/oauth2/v2/auth?${params}`, state, nonce, verifier }
}

/** Đọc code từ redirect URL và kiểm tra state (chống CSRF). */
export function parseAuthRedirect(redirected: string, expectedState: string): string {
  const u = new URL(redirected)
  const err = u.searchParams.get('error')
  if (err) throw new Error(`OAUTH_${err.toUpperCase()}`)
  if (u.searchParams.get('state') !== expectedState) throw new Error('OAUTH_STATE_MISMATCH')
  const code = u.searchParams.get('code')
  if (!code) throw new Error('OAUTH_NO_CODE')
  return code
}
