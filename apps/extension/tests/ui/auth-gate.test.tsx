// @vitest-environment happy-dom
/**
 * P5.S7 — Local mode (ADR-0016 §4.8): AuthGate không có nút Google, hiện "Kết nối lại server"
 * (bấm → gọi auth/status, background tự dev-login); SettingsView ẩn "Đăng xuất" trong local mode.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { installChrome } from '../helpers/chrome'

installChrome()
const rpc = vi.fn()
vi.mock('../../src/shared/messaging/client', () => ({ rpc: (...a: unknown[]) => rpc(...a), onBroadcast: () => () => undefined }))

const { ToastProvider } = await import('../../src/ui/components')
const { AuthGate } = await import('../../src/ui/features/auth/AuthGate')
const { SettingsView } = await import('../../src/ui/features/account/SettingsView')
const wrap = (ui: React.ReactElement) => render(<ToastProvider>{ui}</ToastProvider>)

const user = { id: 'u', email: 'local@quickassist.local', display_name: 'Local', avatar_url: null, created_at: '2026-11-01T00:00:00Z' }
type SessionOver = Partial<{ signedIn: boolean; user: typeof user; authMode: 'google' | 'local' }>
const session = (over: SessionOver) => ({
  signedIn: false, user: null, authMode: 'google' as const, ...over,
})
const FOLDERS = [{ id: 'f1', name: 'Ghi chú' }]

beforeEach(() => {
  rpc.mockReset()
  rpc.mockImplementation(async (type: string) => {
    if (type === 'quota/get') return { billing_mode: 'server', limit_tokens: 1000, used_tokens: 10, reserved_tokens: 0, remaining_tokens: 990 }
    if (type === 'prefs/get') return { defaultFolderId: null }
    if (type === 'folders/list') return FOLDERS
    throw new Error(type)
  })
})
afterEach(cleanup)

describe('AuthGate — local mode', () => {
  it('authMode=local, chưa đăng nhập: KHÔNG nút Google, có "Kết nối lại server" → gọi auth/status', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'auth/status' && rpc.mock.calls.filter((c) => c[0] === 'auth/status').length <= 1)
        return session({ authMode: 'local' })
      if (type === 'auth/status') return session({ authMode: 'local', signedIn: true, user })
      throw new Error(type)
    })
    wrap(<AuthGate>{() => <div>ĐÃ ĐĂNG NHẬP</div>}</AuthGate>)
    expect(await screen.findByText(/chế độ tự host/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Google/ })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Kết nối lại server' }))
    await screen.findByText('ĐÃ ĐĂNG NHẬP') // auth/status lần 2 → signedIn
    expect(rpc.mock.calls.filter((c) => c[0] === 'auth/status')).toHaveLength(2)
  })

  it('authMode=google, chưa đăng nhập: nút Google như cũ → gọi auth/login', async () => {
    rpc.mockImplementation(async (type: string) => {
      if (type === 'auth/login') return session({ signedIn: true, user })
      if (type === 'auth/status') return session({})
      throw new Error(type)
    })
    wrap(<AuthGate>{() => <div>ĐÃ ĐĂNG NHẬP</div>}</AuthGate>)
    expect(screen.queryByRole('button', { name: 'Kết nối lại server' })).toBeNull()
    fireEvent.click(await screen.findByRole('button', { name: /Đăng nhập bằng Google/ }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('auth/login'))
    await screen.findByText('ĐÃ ĐĂNG NHẬP')
  })
})

describe('SettingsView — local mode', () => {
  it('local mode: ẩn "Đăng xuất"', async () => {
    wrap(<SettingsView session={session({ authMode: 'local', signedIn: true, user })} />)
    await screen.findByText(/còn lại/i)
    expect(screen.queryByRole('button', { name: 'Đăng xuất' })).toBeNull()
  })

  it('google mode: hiện "Đăng xuất"', async () => {
    wrap(<SettingsView session={session({ signedIn: true, user })} />)
    await screen.findByText(/còn lại/i)
    expect(screen.getByRole('button', { name: 'Đăng xuất' })).toBeTruthy()
  })
})
