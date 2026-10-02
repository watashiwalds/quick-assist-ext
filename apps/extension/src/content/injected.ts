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

/** Lấy vùng bôi đen hiện tại (dùng cho phím tắt Ctrl+Alt+N). */
export function readSelection(): PageSelection {
  const text = (window.getSelection()?.toString() ?? '').slice(0, 50_000)
  return { text, url: location.href, title: document.title }
}

export type ToastSpec =
  | { kind: 'pending'; pendingId: string; snippet: string; seconds: number }
  | { kind: 'error'; message: string }

/** Toast có đếm ngược + nút Hoàn tác, cô lập CSS bằng Shadow DOM. */
export function renderToast(spec: ToastSpec): void {
  const HOST_ID = 'quickassist-toast-host'
  document.getElementById(HOST_ID)?.remove()
  const host = document.createElement('div')
  host.id = HOST_ID
  host.style.cssText = 'position:fixed;z-index:2147483647;right:16px;bottom:16px;'
  const root = host.attachShadow({ mode: 'closed' })
  const style = document.createElement('style')
  style.textContent = `
    .t{font:14px/1.4 system-ui,sans-serif;background:#1f2328;color:#fff;border-radius:10px;
       padding:12px 14px;max-width:340px;box-shadow:0 8px 24px rgba(0,0,0,.25)}
    .s{opacity:.8;margin:4px 0 8px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}
    .r{display:flex;justify-content:space-between;align-items:center;gap:12px}
    button{font:inherit;background:#fff;color:#1f2328;border:0;border-radius:6px;padding:4px 10px;cursor:pointer}
    button:focus-visible{outline:2px solid #4c8dff;outline-offset:2px}`
  const box = document.createElement('div')
  box.className = 't'
  box.setAttribute('role', 'status')
  root.append(style, box)
  document.documentElement.append(host)

  if (spec.kind === 'error') {
    box.textContent = spec.message
    setTimeout(() => host.remove(), 3500)
    return
  }

  const head = document.createElement('div')
  const snippet = document.createElement('div')
  snippet.className = 's'
  snippet.textContent = `“${spec.snippet}”`
  const row = document.createElement('div')
  row.className = 'r'
  const counter = document.createElement('span')
  const undo = document.createElement('button')
  undo.textContent = 'Hoàn tác (Ctrl+Alt+Z)'
  row.append(counter, undo)
  box.append(head, snippet, row)

  let left = spec.seconds
  const tick = () => {
    head.textContent = 'Đang lưu ghi chú…'
    counter.textContent = `${left}s`
  }
  tick()
  const timer = setInterval(() => {
    left -= 1
    if (left <= 0) {
      clearInterval(timer)
      head.textContent = 'Đã gửi ghi chú ✓'
      row.remove()
      setTimeout(() => host.remove(), 1500)
    } else tick()
  }, 1000)

  const doUndo = () => {
    clearInterval(timer)
    document.removeEventListener('keydown', onKey, true)
    chrome.runtime
      .sendMessage({ channel: 'qa-rpc', type: 'quickNote/undo', payload: { pendingId: spec.pendingId } })
      .then((res: { ok: boolean; data?: { undone: boolean } }) => {
        head.textContent = res?.ok && res.data?.undone ? 'Đã hoàn tác' : 'Không thể hoàn tác (đã gửi)'
        row.remove()
        setTimeout(() => host.remove(), 1500)
      })
      .catch(() => host.remove())
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.ctrlKey && e.altKey && e.key.toLowerCase() === 'z') {
      e.preventDefault()
      doUndo()
    }
  }
  undo.addEventListener('click', doUndo)
  document.addEventListener('keydown', onKey, true)
  setTimeout(() => document.removeEventListener('keydown', onKey, true), spec.seconds * 1000)
}
