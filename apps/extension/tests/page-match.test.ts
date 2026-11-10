// @vitest-environment happy-dom
/**
 * AutoChunk (ADR-0013) — hàm tiêm vào trang: getRawHtml (bỏ thẻ/dữ liệu nhạy cảm, giới hạn kích thước),
 * highlightBlocksByText (khớp theo text bỏ khoảng trắng, occ, contains, fuzzy, thất bại an toàn,
 * không để lại dấu vết trên DOM); background runPageMatch/highlightInTab.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getRawHtml, highlightBlocksByText } from '../src/content/injected'
import { AppError } from '../src/shared/errors'
import { installChrome } from './helpers/chrome'

const { chrome, sent } = installChrome()
const pageMatch = vi.fn()
vi.mock('../src/background/api', () => ({ api: { ai: { pageMatch: (...a: unknown[]) => pageMatch(...a) } } }))
const { runPageMatch, highlightInTab } = await import('../src/background/page-match')

afterEach(() => {
  document.head.innerHTML = ''
  document.body.innerHTML = ''
  vi.useRealTimers()
})

describe('getRawHtml', () => {
  it('bỏ script/style/svg/iframe… và ô nhập ẩn/mật khẩu, không giữ value; không sửa trang thật', () => {
    document.head.innerHTML = '<style>p{color:red}</style><script>window.__NEXT_DATA__={"token":"s3cr3t"}</script>'
    document.body.innerHTML = `
      <article><h1>Tiêu đề</h1><p>Nội dung chính</p></article>
      <noscript>bật js</noscript><template><p>tpl</p></template><svg><text>vẽ</text></svg>
      <iframe data-src="https://ads.example"></iframe>
      <form><input type="hidden" name="csrf" value="tok-123"><input type="password" value="pw">
      <input type="text" value="đã gõ"><textarea>nháp riêng tư</textarea></form>`
    const before = document.documentElement.outerHTML
    const r = getRawHtml(2_000_000)
    expect(r.tooLong).toBe(false)
    expect(r.html.startsWith('<!DOCTYPE html>')).toBe(true)
    expect(r.html).toContain('Nội dung chính')
    for (const leaked of ['s3cr3t', 'color:red', 'bật js', 'tpl', 'vẽ', 'ads.example', 'tok-123', '"pw"', 'đã gõ', 'nháp riêng tư']) {
      expect(r.html).not.toContain(leaked)
    }
    expect(document.documentElement.outerHTML).toBe(before) // làm việc trên bản sao
    expect(r.url).toBe(location.href)
  })

  it('trang vượt giới hạn → tooLong, không trả HTML', () => {
    document.body.innerHTML = `<p>${'a'.repeat(5000)}</p>`
    const r = getRawHtml(1000)
    expect(r).toMatchObject({ tooLong: true, html: '' })
    expect(r.bytes).toBeGreaterThan(1000)
  })
})

describe('highlightBlocksByText', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <ul>
        <li id="a">Nghị quyết 12/2023 về
            quản lý <b>đất đai</b></li>
        <li id="b">Nghị quyết 13/2023 về giáo dục</li>
        <li id="c">Lặp lại</li>
        <li id="d">Lặp lại</li>
      </ul>
      <p id="long">Câu thứ nhất về đất đai. Câu thứ hai về quy hoạch đô thị. Câu thứ ba về giao thông.</p>
      <p id="br">Dòng một<br>dòng hai</p>`
  })

  const hl = () => document.querySelectorAll('[style]')

  it('khớp exact dù khoảng trắng/xuống dòng/thẻ inline khác; chỉ phần tử sâu nhất', () => {
    vi.useFakeTimers()
    const r = highlightBlocksByText([{ text: 'Nghị quyết 12/2023 về quản lý đất đai', occ: 0 }])
    expect(r).toEqual({ ok: true, found: 1, total: 1 })
    expect([...hl()].map((e) => e.id)).toEqual(['a'])
  })

  it('<br> bị Trafilatura đổi thành dấu cách vẫn khớp', () => {
    vi.useFakeTimers()
    expect(highlightBlocksByText([{ text: 'Dòng một dòng hai', occ: 0 }]).ok).toBe(true)
    expect([...hl()].map((e) => e.id)).toEqual(['br'])
  })

  it('occ chọn đúng lần xuất hiện thứ n của text lặp', () => {
    vi.useFakeTimers()
    highlightBlocksByText([{ text: 'Lặp lại', occ: 1 }])
    expect([...hl()].map((e) => e.id)).toEqual(['d'])
  })

  it('contains: mảnh tách câu nằm trong đoạn lớn; fuzzy: 80 ký tự đầu', () => {
    vi.useFakeTimers()
    expect(highlightBlocksByText([{ text: 'Câu thứ hai về quy hoạch đô thị.', occ: 0 }]).ok).toBe(true)
    expect([...hl()].map((e) => e.id)).toEqual(['long'])
    const body = 'Nghị quyết về chính sách hỗ trợ người dân khi Nhà nước thu hồi đất để thực hiện các dự án hạ tầng giao thông trọng điểm'
    document.body.insertAdjacentHTML('beforeend', `<p id="fz">${body} — bản trên trang.</p>`)
    expect(highlightBlocksByText([{ text: `${body} (bản đã được chuẩn hoá khác)`, occ: 0 }]).ok).toBe(true)
    expect([...hl()].map((e) => e.id)).toEqual(['fz'])
  })

  it('nhiều đoạn cùng lúc; không tìm thấy → ok:false, không ném lỗi', () => {
    vi.useFakeTimers()
    const r = highlightBlocksByText([
      { text: 'Nghị quyết 13/2023 về giáo dục', occ: 0 },
      { text: 'Lặp lại', occ: 0 },
      { text: 'đoạn không còn trên trang', occ: 0 },
    ])
    expect(r).toEqual({ ok: true, found: 2, total: 3 })
    expect(highlightBlocksByText([{ text: 'không có', occ: 0 }])).toEqual({ ok: false, found: 0, total: 1 })
    expect(highlightBlocksByText([{ text: '', occ: 0 }]).ok).toBe(false)
  })

  it('tự tắt sau ~4 giây và khôi phục nguyên trạng DOM (không để lại thuộc tính)', () => {
    vi.useFakeTimers()
    document.getElementById('b')!.setAttribute('style', 'color: blue;')
    const before = document.body.innerHTML
    highlightBlocksByText([{ text: 'Nghị quyết 13/2023 về giáo dục', occ: 0 }, { text: 'Lặp lại', occ: 0 }])
    expect(document.body.innerHTML).not.toBe(before)
    vi.advanceTimersByTime(4100)
    expect(document.body.innerHTML).toBe(before)
  })

  it('bấm đoạn khác khi đang nổi bật → tắt lần trước', () => {
    vi.useFakeTimers()
    highlightBlocksByText([{ text: 'Lặp lại', occ: 0 }])
    highlightBlocksByText([{ text: 'Nghị quyết 13/2023 về giáo dục', occ: 0 }])
    expect([...hl()].map((e) => e.id)).toEqual(['b'])
  })
})

describe('background page-match', () => {
  beforeEach(() => {
    pageMatch.mockReset()
    sent.length = 0
    ;(chrome as unknown as { tabs: unknown }).tabs = { query: vi.fn(async () => [{ id: 7 }]) }
  })

  const page = (over = {}) => ({ html: '<!DOCTYPE html><p>x</p>', url: 'https://a.vn/nq', title: 'NQ', bytes: 30, tooLong: false, ...over })

  it('chụp trang → POST /ai/page-match, phát tiến độ, trả kèm tabId/url', async () => {
    chrome.scripting.executeScript.mockResolvedValueOnce([{ result: page() }])
    pageMatch.mockResolvedValueOnce({ mode: 'segments', match_ratio: 0.2, warning: null, items: [], total_chars: 10, truncated: false, full_text: null })
    const r = await runPageMatch('đất đai')
    expect(chrome.scripting.executeScript).toHaveBeenCalledWith(expect.objectContaining({ target: { tabId: 7 }, args: [2_000_000] }))
    expect(pageMatch).toHaveBeenCalledWith({ query: 'đất đai', html: '<!DOCTYPE html><p>x</p>', url: 'https://a.vn/nq', title: 'NQ' })
    expect(r).toMatchObject({ tabId: 7, url: 'https://a.vn/nq', mode: 'segments' })
    expect(sent).toContainEqual({ channel: 'qa-event', type: 'pageMatch/progress', phase: 'analyzing' })
  })

  it('trang quá lớn → PAGE_TOO_LONG, không tải lên', async () => {
    chrome.scripting.executeScript.mockResolvedValueOnce([{ result: page({ html: '', tooLong: true, bytes: 3e6 }) }])
    await expect(runPageMatch('x')).rejects.toMatchObject({ code: 'PAGE_TOO_LONG', status: 413 })
    expect(pageMatch).not.toHaveBeenCalled()
  })

  it('không tiêm được script (chưa có quyền / trang chrome://) → PAGE_ACCESS_DENIED', async () => {
    chrome.scripting.executeScript.mockRejectedValueOnce(new Error('Cannot access contents of the page'))
    await expect(runPageMatch('x')).rejects.toMatchObject({ code: 'PAGE_ACCESS_DENIED' })
    chrome.scripting.executeScript.mockResolvedValueOnce([{ result: page({ url: 'file:///C:/a.html' }) }])
    await expect(runPageMatch('x')).rejects.toMatchObject({ code: 'PAGE_ACCESS_DENIED' })
  })

  it('lỗi API (402/413/422/502) xuyên suốt tới UI', async () => {
    chrome.scripting.executeScript.mockResolvedValueOnce([{ result: page() }])
    pageMatch.mockRejectedValueOnce(new AppError('QUOTA_EXCEEDED', 'hết', 402))
    await expect(runPageMatch('x')).rejects.toMatchObject({ code: 'QUOTA_EXCEEDED', status: 402 })
  })

  it('highlightInTab: tiêm vào đúng tab đã quét; tab đóng → ok:false', async () => {
    chrome.scripting.executeScript.mockResolvedValueOnce([{ result: { ok: true, found: 1, total: 1 } }])
    expect(await highlightInTab(9, [{ text: 'a', occ: 0 }])).toEqual({ ok: true, found: 1, total: 1 })
    expect(chrome.scripting.executeScript).toHaveBeenLastCalledWith(expect.objectContaining({ target: { tabId: 9 } }))
    chrome.scripting.executeScript.mockRejectedValueOnce(new Error('No tab with id'))
    expect(await highlightInTab(9, [{ text: 'a', occ: 0 }])).toEqual({ ok: false, found: 0, total: 1 })
  })
})
