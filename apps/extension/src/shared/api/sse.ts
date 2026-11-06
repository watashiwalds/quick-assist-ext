/**
 * Bộ đọc Server-Sent Events tối giản (chuẩn WHATWG): nhận từng mảnh text bất kỳ độ dài,
 * gom thành sự kiện {event, data}. Dùng cho POST /ai/chat (fetch + ReadableStream — EventSource
 * không gửi được POST/Authorization).
 */
export interface SseEvent {
  event: string
  data: string
}

export function createSseParser(onEvent: (e: SseEvent) => void) {
  let buf = ''
  let event = ''
  let data: string[] = []

  function dispatch() {
    if (data.length) onEvent({ event: event || 'message', data: data.join('\n') })
    event = ''
    data = []
  }

  function line(l: string) {
    if (l === '') return dispatch()
    if (l.startsWith(':')) return // comment / keep-alive
    const i = l.indexOf(':')
    const field = i === -1 ? l : l.slice(0, i)
    let value = i === -1 ? '' : l.slice(i + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }

  return {
    feed(chunk: string) {
      buf += chunk
      let m: RegExpExecArray | null
      const re = /\r\n|\r|\n/g
      let start = 0
      while ((m = re.exec(buf))) {
        // "\r" ở cuối bộ đệm có thể là nửa đầu của "\r\n" → chờ mảnh sau
        if (m[0] === '\r' && m.index === buf.length - 1) break
        line(buf.slice(start, m.index))
        start = m.index + m[0].length
      }
      buf = buf.slice(start)
    },
    /** Kết thúc luồng: xử lý dòng cuối (nếu server không gửi dòng trống cuối cùng). */
    end() {
      if (buf) line(buf)
      buf = ''
      dispatch()
    },
  }
}
