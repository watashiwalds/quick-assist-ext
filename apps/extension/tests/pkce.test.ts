import { describe, expect, it } from 'vitest'
import { buildGoogleAuthRequest, parseAuthRedirect, pkceChallenge } from '../src/shared/pkce'

describe('PKCE', () => {
  it('khớp vector chuẩn RFC 7636 (Appendix B)', async () => {
    expect(await pkceChallenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk')).toBe(
      'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM',
    )
  })

  it('URL đăng nhập có đủ tham số bảo mật, verifier hợp lệ', async () => {
    const r = await buildGoogleAuthRequest('cid', 'https://abc.chromiumapp.org/')
    const u = new URL(r.url)
    expect(u.searchParams.get('code_challenge_method')).toBe('S256')
    expect(u.searchParams.get('scope')).toBe('openid email profile')
    expect(u.searchParams.get('state')).toBe(r.state)
    expect(r.verifier.length).toBeGreaterThanOrEqual(43)
  })

  it('từ chối state sai (chống CSRF)', () => {
    expect(() => parseAuthRedirect('https://x.chromiumapp.org/?code=1&state=evil', 'good')).toThrow(
      'OAUTH_STATE_MISMATCH',
    )
    expect(parseAuthRedirect('https://x.chromiumapp.org/?code=abc&state=good', 'good')).toBe('abc')
  })
})
