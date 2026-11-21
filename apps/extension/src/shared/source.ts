/**
 * Nguồn chi tiết cho ghi chú (ADR-0018): định danh và nhãn nguồn theo URL trang,
 * gom nhóm client-side theo trang (origin + pathname, bỏ ?query và #hash).
 *
 * Quy tắc "raw URL, bỏ modifier": KHÔNG strip `www.`, không xử lý AMP/mobile,
 * không sort query, không danh sách tracking param — chỉ bỏ query/hash.
 * Chỉ nhận http/https (chrome://, file://, about:… → null). Hàm thuần, không I/O.
 */

/** Nguồn tham chiếu khi dán nội dung (PageFinder): tab đang mở hoặc URL nhập tay. */
export interface SourceRef {
  url: string
  title: string
  /** 'tab' = lấy từ tab đang mở; 'manual' = người dùng nhập URL. */
  kind: 'tab' | 'manual'
}

/** Khoá nguồn chi tiết: `origin + pathname` (bỏ query/hash); null nếu URL không hợp lệ. */
export function sourceKey(raw: string | null | undefined): string | null {
  if (!raw) return null
  try {
    const u = new URL(raw.trim())
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null
    // Giữ nguyên host (kể cả www) và pathname (kể cả "/" cuối) theo lựa chọn raw URL.
    return `${u.protocol}//${u.host}${u.pathname}`
  } catch {
    return null
  }
}

/** Hostname của URL (lowercase theo URL parser, giữ www); null nếu không hợp lệ. */
export function sourceDomain(raw: string | null | undefined): string | null {
  if (!raw) return null
  try {
    const u = new URL(raw.trim())
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null
    return u.hostname
  } catch {
    return null
  }
}

/** Nhãn hiển thị: `host + path` (bỏ query/hash, path "/" chỉ còn host); cắt ngắn ở `max`. */
export function sourceLabel(raw: string | null | undefined, max = 80): string | null {
  const key = sourceKey(raw)
  if (!key) return null
  try {
    const u = new URL(key)
    let path = u.pathname
    try {
      path = decodeURIComponent(path)
    } catch {
      // path có % không hợp lệ → dùng nguyên bản, không decode
    }
    const label = `${u.host}${path === '/' ? '' : path}`
    return label.length > max ? `${label.slice(0, max - 1)}…` : label
  } catch {
    return null
  }
}

export interface PageGroup<T> {
  /** Khoá nhóm: sourceKey hoặc `__unknown_page__` khi không có URL hợp lệ. */
  key: string
  /** URL đại diện của nhóm (item đầu tiên); null cho nhóm không rõ trang. */
  url: string | null
  label: string
  items: T[]
}

const UNKNOWN_PAGE_KEY = '__unknown_page__'

/** Gom items theo trang (sourceKey của `url`). Giữ thứ tự xuất hiện; "Không rõ trang" nằm cuối. */
export function groupByPage<T extends { url: string | null }>(items: T[]): PageGroup<T>[] {
  const groups = new Map<string, PageGroup<T>>()
  for (const item of items) {
    const key = sourceKey(item.url) ?? UNKNOWN_PAGE_KEY
    const group = groups.get(key)
    if (group) group.items.push(item)
    else
      groups.set(key, {
        key,
        url: key === UNKNOWN_PAGE_KEY ? null : (item.url ?? null),
        label: sourceLabel(item.url) ?? 'Không rõ trang',
        items: [item],
      })
  }
  const listed = [...groups.values()]
  const known = listed.filter((g) => g.key !== UNKNOWN_PAGE_KEY)
  const unknown = listed.filter((g) => g.key === UNKNOWN_PAGE_KEY)
  return [...known, ...unknown]
}
