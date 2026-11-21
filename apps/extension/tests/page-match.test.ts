// @vitest-environment happy-dom
/**
 * AutoChunk (ADR-0013) — hàm tiêm vào trang: getRawHtml (bỏ thẻ/dữ liệu nhạy cảm, giới hạn kích thước),
 * highlightBlocksByText (khớp theo text bỏ khoảng trắng, occ, contains, fuzzy, thất bại an toàn,
 * không để lại dấu vết trên DOM); background runPageMatch/highlightInTab.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getPageTextChars, getRawHtml, highlightBlocksByText } from '../src/content/injected'
import { AppError } from '../src/shared/errors'
import { installChrome } from './helpers/chrome'

const { chrome, sent } = installChrome()
const pageMatchStream = vi.fn()
vi.mock('../src/background/api', () => ({ api: { ai: { pageMatchStream: (...a: unknown[]) => pageMatchStream(...a) } } }))
const { runPageMatch, highlightInTab, inspectPage, cancelPageMatch, getActiveTabSource } = await import('../src/background/page-match')

/** Response giả cho http.stream: một mảnh SSE chứa toàn bộ event rồi kết thúc. */
function sse(events: Array<[string, unknown]>) {
  const text = events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join('')
  let read = false
  return {
    body: {
      pipeThrough: () => ({
        getReader: () => ({
          read: async () => (read ? { done: true } : ((read = true), { done: false, value: text })),
        }),
      }),
    },
  }
}

const done = (over: Record<string, unknown> = {}) => ({
  mode: 'segments', match_ratio: 0.2, warning: null, items: [], total_chars: 10,
  truncated: false, full_text: null, ...over,
})

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
    // Phase 3: đếm ký tự văn bản sau khi bỏ script/style…, dùng để cảnh báo trước khi quét.
    expect(r.textChars).toBe('Tiêu đềNội dung chính'.length)
  })

  it('getPageTextChars: đếm văn bản nhìn thấy, bỏ script/style và nội dung ô nhập', () => {
    document.body.innerHTML = `
      <p>Đoạn một</p><script>KHONG_DEM</script><style>.x{}</style>
      <textarea>nháp</textarea><p>Đoạn hai</p>`
    expect(getPageTextChars()).toBe('Đoạn một Đoạn hai'.length)
  })

  it('hàm tiêm tự chứa — chạy được khi không có closure của module (bị chuyển sang ngữ cảnh trang)', () => {
    document.body.innerHTML = '<p>Nội dung</p>'
    // `new Function` không giữ closure: nếu hàm còn tham chiếu hằng/biến module thì test này nổ.
    const isolated = (fn: { toString(): string }, ...args: unknown[]) =>
      new Function(`return (${fn.toString()})(...${JSON.stringify(args)})`)() as unknown
    expect(isolated(getPageTextChars)).toBe('Nội dung'.length)
    expect((isolated(getRawHtml, 2_000_000) as { html: string }).html).toContain('Nội dung')
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
    pageMatchStream.mockReset()
    sent.length = 0
    ;(chrome as unknown as { tabs: unknown }).tabs = { query: vi.fn(async () => [{ id: 7, url: 'https://a.vn/nq', title: 'NQ' }]) }
  })

  const page = (over = {}) => ({ html: '<!DOCTYPE html><p>x</p>', url: 'https://a.vn/nq', title: 'NQ', bytes: 30, textChars: 20, tooLong: false, ...over })

  it('chụp trang → stream SSE, phát tiến độ từng bước, trả kèm tabId/url', async () => {
    chrome.scripting.executeScript.mockResolvedValueOnce([{ result: page() }])
    pageMatchStream.mockResolvedValueOnce(sse([
      ['progress', { phase: 'extract' }],
      ['progress', { phase: 'batch', index: 1, total: 2 }],
      ['progress', { phase: 'verify' }],
      ['done', done()],
    ]))
    const r = await runPageMatch({ query: 'đất đai', requestId: 'r1' })
    expect(chrome.scripting.executeScript).toHaveBeenCalledWith(expect.objectContaining({ target: { tabId: 7 }, args: [2_000_000] }))
    expect(pageMatchStream).toHaveBeenCalledWith(
      { query: 'đất đai', html: '<!DOCTYPE html><p>x</p>', url: 'https://a.vn/nq', title: 'NQ', scan_all: false },
      expect.any(AbortSignal),
    )
    expect(r).toMatchObject({ tabId: 7, url: 'https://a.vn/nq', mode: 'segments' })
    expect(sent).toContainEqual({ channel: 'qa-event', type: 'pageMatch/progress', phase: 'extract' })
    expect(sent).toContainEqual({ channel: 'qa-event', type: 'pageMatch/progress', phase: 'batch', index: 1, total: 2 })
    expect(sent).toContainEqual({ channel: 'qa-event', type: 'pageMatch/progress', phase: 'verify' })
  })

  it('nguồn dán → không chụp trang, gửi text + scan_all, kết quả không có tabId/url', async () => {
    chrome.scripting.executeScript.mockClear()
    pageMatchStream.mockResolvedValueOnce(sse([['done', done()]]))
    const r = await runPageMatch({ query: 'đất đai', text: 'Đoạn một.\n\nĐoạn hai.', scanAll: true })
    expect(chrome.scripting.executeScript).not.toHaveBeenCalled()
    expect(pageMatchStream).toHaveBeenCalledWith(
      { query: 'đất đai', text: 'Đoạn một.\n\nĐoạn hai.', url: null, title: null, scan_all: true },
      expect.any(AbortSignal),
    )
    expect(r.tabId).toBeUndefined()
    expect(r).toMatchObject({ url: null, title: null, mode: 'segments' })
  })

  it('nguồn dán có nguồn tham chiếu (ADR-0018) → gửi url/title, trả lại trong kết quả', async () => {
    pageMatchStream.mockResolvedValueOnce(sse([['done', done()]]))
    const r = await runPageMatch({ query: 'đất đai', text: 'Nội dung dán', url: 'https://vnexpress.net/bai?utm=x', title: 'Bài báo' })
    expect(pageMatchStream).toHaveBeenCalledWith(
      { query: 'đất đai', text: 'Nội dung dán', url: 'https://vnexpress.net/bai?utm=x', title: 'Bài báo', scan_all: false },
      expect.any(AbortSignal),
    )
    expect(r.tabId).toBeUndefined()
    expect(r).toMatchObject({ url: 'https://vnexpress.net/bai?utm=x', title: 'Bài báo' })
  })

  it('getActiveTabSource: tab http(s) → url/title; chrome://, file://, không URL → null', async () => {
    const tabs = chrome.tabs.query as ReturnType<typeof vi.fn>
    tabs.mockResolvedValueOnce([{ id: 7, url: 'https://a.vn/bai', title: 'Bài' }])
    await expect(getActiveTabSource()).resolves.toEqual({ url: 'https://a.vn/bai', title: 'Bài' })
    tabs.mockResolvedValueOnce([{ id: 7, url: 'chrome://extensions', title: 'Extensions' }])
    await expect(getActiveTabSource()).resolves.toBeNull()
    tabs.mockResolvedValueOnce([{ id: 7, url: 'file:///C:/a.pdf', title: 'PDF' }])
    await expect(getActiveTabSource()).resolves.toBeNull()
    tabs.mockResolvedValueOnce([{ id: 7 }])
    await expect(getActiveTabSource()).resolves.toBeNull()
    tabs.mockResolvedValueOnce([])
    await expect(getActiveTabSource()).resolves.toBeNull()
  })

  it('nguồn dán rỗng → PAGE_NO_CONTENT, không gọi API', async () => {
    await expect(runPageMatch({ query: 'x', text: '   ' })).rejects.toMatchObject({ code: 'PAGE_NO_CONTENT', status: 422 })
    expect(pageMatchStream).not.toHaveBeenCalled()
  })

  it('server phát event error → AppError tương ứng xuyên suốt tới UI', async () => {
    pageMatchStream.mockResolvedValueOnce(sse([['error', { code: 'QUOTA_EXCEEDED', message: 'hết', status: 402 }]]))
    await expect(runPageMatch({ query: 'x', text: 'nội dung' })).rejects.toMatchObject({ code: 'QUOTA_EXCEEDED', status: 402 })
  })

  it('stream đóng mà không có done → NETWORK_ERROR', async () => {
    pageMatchStream.mockResolvedValueOnce(sse([['progress', { phase: 'extract' }]]))
    await expect(runPageMatch({ query: 'x', text: 'nội dung' })).rejects.toMatchObject({ code: 'NETWORK_ERROR' })
  })

  it('huỷ giữa chừng → abort signal của fetch và báo ABORTED', async () => {
    pageMatchStream.mockImplementationOnce(async (_b: unknown, signal: AbortSignal) =>
      await new Promise((_, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      }))
    const p = runPageMatch({ query: 'x', text: 'nội dung', requestId: 'req-1' })
    await vi.waitFor(() => expect(pageMatchStream).toHaveBeenCalled())
    cancelPageMatch('req-1')
    await expect(p).rejects.toMatchObject({ code: 'ABORTED' })
  })

  it('trang quá lớn → PAGE_TOO_LONG, không tải lên', async () => {
    chrome.scripting.executeScript.mockResolvedValueOnce([{ result: page({ html: '', tooLong: true, bytes: 3e6 }) }])
    await expect(runPageMatch({ query: 'x' })).rejects.toMatchObject({ code: 'PAGE_TOO_LONG', status: 413 })
    expect(pageMatchStream).not.toHaveBeenCalled()
  })

  it('không tiêm được script (chưa có quyền / trang chrome://) → PAGE_ACCESS_DENIED', async () => {
    chrome.scripting.executeScript.mockRejectedValueOnce(new Error('Cannot access contents of the page'))
    await expect(runPageMatch({ query: 'x' })).rejects.toMatchObject({ code: 'PAGE_ACCESS_DENIED' })
    chrome.scripting.executeScript.mockResolvedValueOnce([{ result: page({ url: 'file:///C:/a.html' }) }])
    await expect(runPageMatch({ query: 'x' })).rejects.toMatchObject({ code: 'PAGE_ACCESS_DENIED' })
  })

  it('inspectPage: trả textChars + metadata tab, không tải HTML', async () => {
    chrome.scripting.executeScript.mockResolvedValueOnce([{ result: 123_456 }])
    expect(await inspectPage()).toEqual({ textChars: 123_456, url: 'https://a.vn/nq', title: 'NQ' })
    expect(chrome.scripting.executeScript).toHaveBeenLastCalledWith(
      expect.objectContaining({ target: { tabId: 7 }, func: getPageTextChars }),
    )
  })

  it('highlightInTab: tiêm vào đúng tab đã quét; tab đóng → ok:false', async () => {
    chrome.scripting.executeScript.mockResolvedValueOnce([{ result: { ok: true, found: 1, total: 1 } }])
    expect(await highlightInTab(9, [{ text: 'a', occ: 0 }])).toEqual({ ok: true, found: 1, total: 1 })
    expect(chrome.scripting.executeScript).toHaveBeenLastCalledWith(expect.objectContaining({ target: { tabId: 9 } }))
    chrome.scripting.executeScript.mockRejectedValueOnce(new Error('No tab with id'))
    expect(await highlightInTab(9, [{ text: 'a', occ: 0 }])).toEqual({ ok: false, found: 0, total: 1 })
  })
})
