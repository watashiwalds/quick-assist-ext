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
