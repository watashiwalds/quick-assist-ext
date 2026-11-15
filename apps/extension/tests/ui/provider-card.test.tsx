// @vitest-environment happy-dom
/**
 * P4 — Card "Nhà cung cấp AI" (ADR-0016 §6.2) với RPC giả lập:
 * preset điền mẫu, kiểm tra kết nối hiện kết quả, Lưu có ConfirmDialog khi đổi hàm embedding,
 * key không bao giờ rời form (không log, không storage), BYOK → nút "Dùng cấu hình server".
 */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { installChrome } from '../helpers/chrome'

installChrome()
const rpc = vi.fn()
vi.mock('../../src/shared/messaging/client', () => ({ rpc: (...a: unknown[]) => rpc(...a), onBroadcast: () => () => undefined }))

const { ToastProvider } = await import('../../src/ui/components')
const { ProviderCard } = await import('../../src/ui/features/account/ProviderCard')
const wrap = (ui: React.ReactElement) => render(<ToastProvider>{ui}</ToastProvider>)

const serverCfg = {
  mode: 'inherit', provider: null, base_url: null, has_key: false, key_hint: null,
  chat_model: null, embedding_model: null, timeout_seconds: null, rebuild_note_count: 3,
  server_default: { provider: 'gemini', chat_model: 'gemma-4-31b-it', embedding_model: 'gemini-embedding-001' },
  rebuild: null,
}
const byokCfg = {
  ...serverCfg,
  mode: 'byok', provider: 'openai', base_url: 'http://localhost:11434/v1', has_key: true,
  key_hint: 'a1b2', chat_model: 'llama3.1', embedding_model: 'nomic-embed-text', timeout_seconds: 180,
}
const savedCfg = (over: Record<string, unknown> = {}) => ({ ...byokCfg, ...over, rebuild: null })

const type = async (label: string | RegExp, value: string) =>
  fireEvent.change(await screen.findByLabelText(label), { target: { value } })

beforeEach(() => {
  rpc.mockReset()
  rpc.mockImplementation(async (t: string) => {
    if (t === 'ai/config/get') return byokCfg
    throw new Error(t)
  })
})
afterEach(cleanup)

describe('Nhà cung cấp AI (ADR-0016)', () => {
  it('preset điền base_url + model gợi ý, mọi ô vẫn sửa được', async () => {
    rpc.mockImplementation(async (t: string) => (t === 'ai/config/get' ? serverCfg : Promise.reject(new Error(t))))
    wrap(<ProviderCard />)
    fireEvent.change(await screen.findByLabelText('Mẫu cấu hình'), { target: { value: 'ollama' } })
    expect((await screen.findByLabelText(/Base URL/) as HTMLInputElement).value).toBe('http://localhost:11434/v1')
    expect((screen.getByLabelText('Model chat') as HTMLInputElement).value).toBe('llama3.1')
    expect((screen.getByLabelText('Model embedding') as HTMLInputElement).value).toBe('nomic-embed-text')
    // sửa tay vẫn được
    await type(/Base URL/, 'http://192.168.1.10:11434/v1')
    expect((screen.getByLabelText(/Base URL/) as HTMLInputElement).value).toBe('http://192.168.1.10:11434/v1')
  })

  it('kiểm tra kết nối: hiện dim native + padded + latency, không gọi Lưu', async () => {
    rpc.mockImplementation(async (t: string) => {
      if (t === 'ai/config/get') return byokCfg
      if (t === 'ai/config/test')
        return { ok: true, embedding: { model: 'nomic-embed-text', dim: 768, padded: true, latency_ms: 412 }, chat: { model: 'llama3.1', latency_ms: 903, sample: 'Hà Nội' } }
      throw new Error(t)
    })
    wrap(<ProviderCard />)
    fireEvent.click(await screen.findByRole('button', { name: 'Kiểm tra kết nối' }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('ai/config/test', expect.objectContaining({ provider: 'openai' })))
    expect(await screen.findByText(/768 chiều/)).toBeTruthy()
    expect(screen.getByText(/pad về 1536/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Lưu và dựng lại' })).toBeNull()
  })

  it('lưu khi đổi model embedding → ConfirmDialog đúng N note → set + banner rebuild', async () => {
    rpc.mockImplementation(async (t: string) => {
      if (t === 'ai/config/get') return byokCfg
      if (t === 'ai/config/set')
        return { ...savedCfg(), embedding_model: 'bge-m3', rebuild: { required: true, notes: 3 } }
      throw new Error(t)
    })
    wrap(<ProviderCard />)
    await type('Model embedding', 'bge-m3')
    fireEvent.click(await screen.findByRole('button', { name: 'Lưu' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Lưu và dựng lại' }))
    await waitFor(() =>
      expect(rpc).toHaveBeenCalledWith('ai/config/set', expect.objectContaining({ embedding_model: 'bge-m3', api_key: null })))
    expect(await screen.findByText(/Đang dựng lại chỉ mục ngữ nghĩa của 3 ghi chú/)).toBeTruthy()
  })

  it('lưu khi chỉ đổi chat model → không hiện dialog, gửi ngay', async () => {
    rpc.mockImplementation(async (t: string) => {
      if (t === 'ai/config/get') return byokCfg
      if (t === 'ai/config/set') return savedCfg({ chat_model: 'llama3.2' })
      throw new Error(t)
    })
    wrap(<ProviderCard />)
    await type('Model chat', 'llama3.2')
    fireEvent.click(await screen.findByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('ai/config/set', expect.objectContaining({ chat_model: 'llama3.2' })))
    expect(screen.queryByText(/Dựng lại chỉ mục/)).toBeNull()
  })

  it('key: gõ mới → gửi chuỗi; bỏ trống → null (giữ key cũ); Xoá key → chuỗi rỗng; không bao giờ nằm trong RPC khác', async () => {
    let savedKey: string | null | undefined = undefined
    rpc.mockImplementation(async (t: string, b?: { api_key?: string | null }) => {
      if (t === 'ai/config/get') return byokCfg
      if (t === 'ai/config/set') {
        savedKey = b?.api_key
        return savedCfg(savedKey === '' ? { has_key: false, key_hint: null } : {})
      }
      throw new Error(t)
    })
    wrap(<ProviderCard />)
    await type('API key', 'sk-brand-new')
    fireEvent.click(await screen.findByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(savedKey).toBe('sk-brand-new'))

    await type('API key', '')
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(savedKey).toBe(null)) // không gõ mà đã có key → giữ key cũ

    fireEvent.click(await screen.findByRole('button', { name: 'Xoá key' }))
    expect(await screen.findByText(/Sẽ XOÁ key đã lưu/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(savedKey).toBe('')) // xoá key khỏi DB
    expect(await screen.findByText(/Không bắt buộc với model tự host/)).toBeTruthy()
  })

  it('BYOK: nút Dùng cấu hình server + confirm → reset', async () => {
    rpc.mockImplementation(async (t: string) => {
      if (t === 'ai/config/get') return byokCfg
      if (t === 'ai/config/reset') return { ...serverCfg, rebuild: { required: true, notes: 3 } }
      throw new Error(t)
    })
    wrap(<ProviderCard />)
    fireEvent.click(await screen.findByRole('button', { name: 'Dùng cấu hình server' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Chuyển và dựng lại' }))
    await waitFor(() => expect(rpc).toHaveBeenCalledWith('ai/config/reset'))
    expect(await screen.findByText(/Đang dựng lại/)).toBeTruthy()
  })

  it('server config: test lỗi trả nguyên nhân (http 401)', async () => {
    rpc.mockImplementation(async (t: string) => {
      if (t === 'ai/config/get') return serverCfg
      if (t === 'ai/config/test') return { ok: false, stage: 'embedding', code: 'AI_PROVIDER_ERROR', message: 'http 401' }
      throw new Error(t)
    })
    wrap(<ProviderCard />)
    await type(/Base URL/, 'https://api.openai.com/v1')
    await type('Model chat', 'gpt-4o-mini')
    await type('Model embedding', 'text-embedding-3-small')
    fireEvent.click(await screen.findByRole('button', { name: 'Kiểm tra kết nối' }))
    expect(await screen.findByText(/http 401/)).toBeTruthy()
  })

  it('>1536: test trả embedding_dim 4096 → chặn Lưu, banner lỗi, không gọi ai/config/set', async () => {
    rpc.mockImplementation(async (t: string) => {
      if (t === 'ai/config/get') return byokCfg
      if (t === 'ai/config/test')
        return { ok: false, embedding_dim: 4096, stage: 'embedding', code: 'AI_PROVIDER_ERROR', message: 'Model embedding trả 4096 chiều…' }
      throw new Error(t)
    })
    wrap(<ProviderCard />)
    fireEvent.click(await screen.findByRole('button', { name: 'Kiểm tra kết nối' }))
    expect(await screen.findByText(/không thể lưu/)).toBeTruthy()
    const save = screen.getByRole('button', { name: 'Lưu' }) as HTMLButtonElement
    expect(save.disabled).toBe(true)
    fireEvent.click(save)
    expect(rpc).not.toHaveBeenCalledWith('ai/config/set', expect.anything())
  })

  it('test 768 → Lưu gửi embedding_dim: 768', async () => {
    rpc.mockImplementation(async (t: string) => {
      if (t === 'ai/config/get') return byokCfg
      if (t === 'ai/config/test')
        return { ok: true, embedding_dim: 768, embedding: { model: 'nomic-embed-text', dim: 768, padded: true, latency_ms: 412 }, chat: { model: 'llama3.1', latency_ms: 903, sample: 'Hà Nội' } }
      if (t === 'ai/config/set') return savedCfg()
      throw new Error(t)
    })
    wrap(<ProviderCard />)
    fireEvent.click(await screen.findByRole('button', { name: 'Kiểm tra kết nối' }))
    await screen.findByText(/768 chiều/)
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }))
    await waitFor(() =>
      expect(rpc).toHaveBeenCalledWith('ai/config/set', expect.objectContaining({ embedding_dim: 768 })))
  })

  it('đổi model sau khi test → banner chưa kiểm tra; Lưu vẫn gọi set nhưng KHÔNG gửi dim cũ', async () => {
    rpc.mockImplementation(async (t: string) => {
      if (t === 'ai/config/get') return byokCfg
      if (t === 'ai/config/test')
        return { ok: true, embedding_dim: 768, embedding: { model: 'nomic-embed-text', dim: 768, padded: true, latency_ms: 412 }, chat: { model: 'llama3.1', latency_ms: 903, sample: 'Hà Nội' } }
      if (t === 'ai/config/set') return savedCfg({ embedding_model: 'bge-m3', rebuild: { required: true, notes: 3 } })
      throw new Error(t)
    })
    wrap(<ProviderCard />)
    fireEvent.click(await screen.findByRole('button', { name: 'Kiểm tra kết nối' }))
    await screen.findByText(/768 chiều/)
    await type('Model embedding', 'bge-m3')
    expect(screen.queryByText(/chưa được kiểm tra/)).toBeNull() // chưa bấm Lưu → chưa cảnh báo
    fireEvent.click(await screen.findByRole('button', { name: 'Lưu' }))
    expect(await screen.findByText(/chưa được kiểm tra/)).toBeTruthy()
    fireEvent.click(await screen.findByRole('button', { name: 'Lưu và dựng lại' }))
    await waitFor(() =>
      expect(rpc).toHaveBeenCalledWith('ai/config/set',
        expect.objectContaining({ embedding_model: 'bge-m3', embedding_dim: undefined })))
    // không gửi dim 768 cũ (model đã đổi)
    expect(rpc).not.toHaveBeenCalledWith('ai/config/set', expect.objectContaining({ embedding_dim: 768 }))
  })
})
