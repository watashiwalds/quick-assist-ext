/**
 * Hàm được background TIÊM vào trang qua chrome.scripting.executeScript({ func }).
 *
 * QUY TẮC: mỗi hàm phải TỰ CHỨA HOÀN TOÀN — không dùng import, biến ngoài, hay
 * helper chung, vì Chrome tuần tự hoá thân hàm và chạy trong ngữ cảnh trang.
 * Nội dung trang là dữ liệu không tin cậy: chỉ dùng textContent, không innerHTML.
 */

export interface PageSelection {
  text: string
  url: string
  title: string
}

/** Lấy vùng bôi đen hiện tại (dùng cho phím tắt Alt+Shift+N) — kể cả trong ô input/textarea. */
export function readSelection(): PageSelection {
  const LIMIT = 50_000
  let text = ''
  const el = document.activeElement as HTMLInputElement | HTMLTextAreaElement | null
  const isField = !!el && (el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && /^(text|search|url|email)?$/i.test(el.type)))
  if (isField && el && typeof el.selectionStart === 'number' && el.selectionEnd !== el.selectionStart) {
    text = el.value.slice(el.selectionStart, el.selectionEnd ?? el.selectionStart)
  } else {
    text = window.getSelection()?.toString() ?? ''
  }
  return { text: text.slice(0, LIMIT), url: location.href, title: document.title }
}

export type ToastSpec =
  | { kind: 'pending'; pendingId: string; snippet: string; seconds: number; folderName?: string; note?: string }
  | { kind: 'error'; message: string }

/** Toast có đếm ngược + nút Hoàn tác, cô lập CSS bằng Shadow DOM (N02). */
export function renderToast(spec: ToastSpec): void {
  const HOST_ID = 'quickassist-toast-host'
  document.getElementById(HOST_ID)?.remove()
  const host = document.createElement('div')
  host.id = HOST_ID
  // all:initial → CSS của trang không ảnh hưởng host; mọi style thật nằm trong shadow root.
  host.style.cssText = 'all:initial;position:fixed;z-index:2147483647;right:16px;bottom:16px;'
  const root = host.attachShadow({ mode: 'closed' })
  const style = document.createElement('style')
  style.textContent = `
    .t{font:14px/1.4 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;background:#1f2328;color:#fff;
       border-radius:10px;padding:12px 14px;max-width:340px;box-shadow:0 8px 24px rgba(0,0,0,.25)}
    .h{font-weight:600}
    .s{opacity:.85;margin:4px 0 8px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}
    .n{font-size:12px;color:#ffd38a;margin-bottom:6px}
    .r{display:flex;justify-content:space-between;align-items:center;gap:12px}
    button{font:inherit;background:#fff;color:#1f2328;border:0;border-radius:6px;padding:4px 10px;cursor:pointer}
    button:focus-visible{outline:2px solid #4c8dff;outline-offset:2px}`
  const box = document.createElement('div')
  box.className = 't'
  box.setAttribute('role', 'status')
  box.setAttribute('aria-live', 'polite')
  root.append(style, box)
  document.documentElement.append(host)

  if (spec.kind === 'error') {
    box.textContent = spec.message
    setTimeout(() => host.remove(), 3500)
    return
  }

  const head = document.createElement('div')
  head.className = 'h'
  const snippet = document.createElement('div')
  snippet.className = 's'
  snippet.textContent = `“${spec.snippet}”`
  const row = document.createElement('div')
  row.className = 'r'
  const counter = document.createElement('span')
  const undo = document.createElement('button')
  undo.type = 'button'
  undo.textContent = 'Hoàn tác (Alt+Shift+Z)'
  row.append(counter, undo)
  box.append(head, snippet)
  if (spec.note) {
    const n = document.createElement('div')
    n.className = 'n'
    n.textContent = spec.note
    box.append(n)
  }
  box.append(row)
  const where = spec.folderName ? ` vào “${spec.folderName}”` : ''

  let left = spec.seconds
  const tick = () => {
    head.textContent = `Đang lưu ghi chú${where}…`
    counter.textContent = `${left}s`
  }
  tick()
  let done = false
  const finish = (text: string) => {
    done = true
    clearInterval(timer)
    document.removeEventListener('keydown', onKey, true)
    head.textContent = text
    row.remove()
    setTimeout(() => host.remove(), 1500)
  }
  const timer = setInterval(() => {
    left -= 1
    if (left <= 0) finish(`Đã lưu ghi chú${where} ✓`)
    else tick()
  }, 1000)

  const doUndo = () => {
    if (done) return
    clearInterval(timer)
    chrome.runtime
      .sendMessage({ channel: 'qa-rpc', type: 'quickNote/undo', payload: { pendingId: spec.pendingId } })
      .then((res: { ok: boolean; data?: { undone: boolean } }) =>
        finish(res?.ok && res.data?.undone ? 'Đã hoàn tác — ghi chú không được lưu' : 'Không thể hoàn tác (đã gửi)'),
      )
      .catch(() => finish('Không thể hoàn tác'))
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.altKey && e.shiftKey && !e.ctrlKey && e.code === 'KeyZ') {
      e.preventDefault()
      e.stopPropagation()
      doUndo()
    }
  }
  undo.addEventListener('click', doUndo)
  document.addEventListener('keydown', onKey, true)
}

// ============================================================ AutoChunk — "Tìm trong trang" (ADR-0013)

export interface RawPage {
  /** HTML đã bỏ script/style/noscript/template/svg/iframe/canvas + input ẩn/mật khẩu; '' khi tooLong */
  html: string
  url: string
  title: string
  bytes: number
  /** HTML vượt giới hạn → background dừng sớm, không tải lên */
  tooLong: boolean
}

/**
 * Chụp HTML trang hiện tại để backend (Trafilatura) trích nội dung chính. Làm việc trên BẢN SAO DOM —
 * không đụng trang thật. Bỏ thẻ không mang nội dung + dữ liệu nhạy cảm dễ lộ (`__NEXT_DATA__`,
 * token form ẩn) trước khi rời máy (AD-3). Không giữ lại thuộc tính `value` của ô nhập.
 */
export function getRawHtml(maxBytes: number): RawPage {
  const clone = document.documentElement.cloneNode(true) as HTMLElement
  const DROP = 'script,style,noscript,template,svg,iframe,canvas,object,embed,link,meta,input[type=hidden],input[type=password]'
  clone.querySelectorAll(DROP).forEach((n) => n.remove())
  clone.querySelectorAll('input,textarea').forEach((n) => {
    n.removeAttribute('value')
    if (n.tagName === 'TEXTAREA') n.textContent = ''
  })
  const html = '<!DOCTYPE html>' + clone.outerHTML
  const bytes = new TextEncoder().encode(html).length
  const tooLong = bytes > maxBytes
  return { html: tooLong ? '' : html, url: location.href, title: document.title, bytes, tooLong }
}

export interface HighlightTarget {
  text: string
  occ: number
}

export interface HighlightResult {
  ok: boolean
  found: number
  total: number
}

/**
 * Tìm lại các đoạn (do backend trích) trên DOM trang → cuộn tới đoạn đầu + làm nổi bật ~4 giây (AD-7).
 *
 * So khớp theo text đã BỎ MỌI KHOẢNG TRẮNG (Trafilatura chuẩn hoá khoảng trắng, <br> thành dấu cách…):
 *   exact (phần tử có đúng text đó) → contains (mảnh tách câu nằm trong phần tử lớn)
 *   → fuzzy (80 ký tự đầu, phương án cuối). Lấy phần tử SÂU NHẤT, đúng lần xuất hiện thứ `occ`.
 * Không gắn thuộc tính / không innerHTML vào DOM trang: dùng CSS Custom Highlight API +
 * adoptedStyleSheets (không tạo node); trình duyệt cũ → outline inline tạm thời rồi khôi phục.
 */
export function highlightBlocksByText(items: HighlightTarget[]): HighlightResult {
  const DURATION = 4000
  const NAME = 'quickassist-match'
  const squash = (s: string) => s.replace(/\s+/g, '')
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'SVG', 'HEAD'])

  const all: Array<{ el: Element; text: string }> = []
  const walker = document.createTreeWalker(document.body ?? document.documentElement, NodeFilter.SHOW_ELEMENT, {
    acceptNode: (n) => (SKIP.has((n as Element).tagName.toUpperCase()) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  })
  for (let n = walker.currentNode as Element | null; n; n = walker.nextNode() as Element | null) {
    if (n.nodeType === 1) all.push({ el: n, text: squash(n.textContent ?? '') })
  }
  /** Phần tử sâu nhất thoả `test` (bỏ phần tử cha nếu con của nó cũng thoả), theo thứ tự tài liệu. */
  const deepest = (test: (t: string) => boolean): Element[] => {
    const hits = all.filter((x) => x.text.length > 0 && test(x.text)).map((x) => x.el)
    return hits.filter((el) => !hits.some((o) => o !== el && el.contains(o)))
  }
  const pick = (target: string, occ: number): Element | null => {
    if (!target) return null
    const head = target.slice(0, 80)
    const passes: Array<(t: string) => boolean> = [(t) => t === target, (t) => t.includes(target)]
    if (head.length >= 20 && head.length < target.length) passes.push((t) => t.includes(head))
    for (const test of passes) {
      const found = deepest(test)
      if (found.length) return found[Math.min(Math.max(occ, 0), found.length - 1)] ?? null
    }
    return null
  }

  const els: Element[] = []
  for (const it of items) {
    const el = pick(squash(it.text ?? ''), it.occ ?? 0)
    if (el && !els.includes(el)) els.push(el)
  }
  if (els.length === 0) return { ok: false, found: 0, total: items.length }

  const w = window as unknown as { __qaHighlightUndo?: () => void }
  w.__qaHighlightUndo?.() // tắt lần nổi bật trước (bấm liên tiếp nhiều đoạn)
  const cssApi = (globalThis as unknown as { CSS?: { highlights?: Map<string, unknown> } }).CSS
  const HighlightCtor = (globalThis as unknown as { Highlight?: new (...r: Range[]) => unknown }).Highlight
  let undo: () => void
  if (cssApi?.highlights && HighlightCtor && 'adoptedStyleSheets' in document) {
    const ranges = els.map((el) => {
      const r = document.createRange()
      r.selectNodeContents(el)
      return r
    })
    cssApi.highlights.set(NAME, new HighlightCtor(...ranges))
    const sheet = new CSSStyleSheet()
    sheet.replaceSync(`::highlight(${NAME}){background-color:#ffe066;color:#111}`)
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]
    undo = () => {
      cssApi.highlights?.delete(NAME)
      document.adoptedStyleSheets = document.adoptedStyleSheets.filter((s) => s !== sheet)
    }
  } else {
    const saved = els.map((el) => {
      const prev = el.getAttribute('style') // khôi phục nguyên trạng, kể cả "không có thuộc tính style"
      const s = (el as HTMLElement).style
      s.outline = '3px solid #f5a524'
      s.outlineOffset = '2px'
      s.backgroundColor = 'rgba(255,224,102,.45)'
      return () => {
        if (prev === null) el.removeAttribute('style')
        else el.setAttribute('style', prev)
      }
    })
    undo = () => saved.forEach((f) => f())
  }
  const timer = setTimeout(() => {
    undo()
    w.__qaHighlightUndo = undefined
  }, DURATION)
  w.__qaHighlightUndo = () => {
    clearTimeout(timer)
    undo()
    w.__qaHighlightUndo = undefined
  }
  ;(els[0] as HTMLElement).scrollIntoView?.({ block: 'center', behavior: 'smooth' })
  return { ok: true, found: els.length, total: items.length }
}
