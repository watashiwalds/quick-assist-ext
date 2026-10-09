import { describe, expect, it, vi } from 'vitest'

import { config } from '../src/shared/config'
import { createApi } from '../src/shared/api/endpoints'
import type { HttpRequest } from '../src/shared/api/http'
import { userMessage } from '../src/shared/errors'

describe('AI request timeout and messages', () => {
  it('gives a summary request its longer AI timeout', async () => {
    const request = vi.fn().mockResolvedValue({ summary: 'x', tokens_used: 1, request_id: 'r' })
    const api = createApi(request as unknown as HttpRequest)

    await api.ai.summarize({ text: 'Nội dung cần tóm tắt' })

    expect(request).toHaveBeenCalledWith('/ai/summaries', {
      method: 'POST',
      body: { text: 'Nội dung cần tóm tắt' },
      timeoutMs: config.summaryRequestTimeoutMs,
    })
  })

  it('does not claim that an AI summary will be queued after a network error', () => {
    expect(userMessage({ code: 'NETWORK_ERROR', message: 'offline', status: 0 })).not.toMatch(/gửi lại/i)
  })
})
