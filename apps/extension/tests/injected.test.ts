// @vitest-environment happy-dom
/** N01 + N02 — hàm tiêm vào trang: đọc vùng chọn (kể cả ô nhập), toast Shadow DOM + Hoàn tác. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readSelection, renderToast } from '../src/content/injected'
import { installChrome } from './helpers/chrome'

describe('readSelection', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('lấy vùng chọn trong textarea (window.getSelection không thấy)', () => {
    const ta = document.createElement('textarea')
    ta.value = 'xin chào thế giới'
    document.body.append(ta)
    ta.focus()
    ta.setSelectionRange(4, 9)
    expect(readSelection().text).toBe('chào ')
    expect(readSelection().url).toBe(location.href)
  })

  it('lấy vùng bôi đen thường trên trang và giới hạn độ dài', () => {
    const p = document.createElement('p')
    p.textContent = 'a'.repeat(60_000)
    document.body.append(p)
    const r = document.createRange()
    r.selectNodeContents(p)
    window.getSelection()!.removeAllRanges()
    window.getSelection()!.addRange(r)
    expect(readSelection().text.length).toBe(50_000)
  })
})

describe('renderToast', () => {
  let chrome: ReturnType<typeof installChrome>['chrome']
  beforeEach(() => {
    vi.useFakeTimers()
    chrome = installChrome().chrome
    document.body.innerHTML = ''
  })
  afterEach(() => vi.useRealTimers())

  it('chỉ có 1 host, CSS trang không ảnh hưởng (all:initial + Shadow DOM)', () => {
    renderToast({ kind: 'error', message: 'Lỗi' })
    renderToast({ kind: 'error', message: 'Lỗi 2' })
    const hosts = document.querySelectorAll('#quickassist-toast-host')
    expect(hosts.length).toBe(1)
    expect((hosts[0] as HTMLElement).style.cssText).toContain('all: initial')
    vi.advanceTimersByTime(4000)
    expect(document.getElementById('quickassist-toast-host')).toBeNull()
  })

  it('Alt+Shift+Z gửi RPC hoàn tác đúng pendingId', async () => {
    chrome.runtime.sendMessage.mockResolvedValue({ ok: true, data: { undone: true } })
    renderToast({ kind: 'pending', pendingId: 'p-1', snippet: 's', seconds: 5, folderName: 'Inbox' })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Z', code: 'KeyZ', shiftKey: true, altKey: true, bubbles: true }))
    expect(chrome.runtime.sendMessage).toHaveBeenCalledWith({ channel: 'qa-rpc', type: 'quickNote/undo', payload: { pendingId: 'p-1' } })
  })

  it('hết giờ thì phím tắt không còn tác dụng', () => {
    renderToast({ kind: 'pending', pendingId: 'p-2', snippet: 's', seconds: 2 })
    vi.advanceTimersByTime(2500)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Z', code: 'KeyZ', shiftKey: true, altKey: true, bubbles: true }))
    expect(chrome.runtime.sendMessage).not.toHaveBeenCalled()
  })

  it('không dùng innerHTML: nội dung trang hiển thị dạng text', () => {
    renderToast({ kind: 'error', message: '<img src=x onerror=alert(1)>' })
    expect(document.querySelector('img')).toBeNull()
  })
})
