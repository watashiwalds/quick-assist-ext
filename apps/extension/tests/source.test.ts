/** ADR-0018 — quy tắc nguồn chi tiết: sourceKey/sourceDomain/sourceLabel/groupByPage. */
import { describe, expect, it } from 'vitest'
import { groupByPage, sourceDomain, sourceKey, sourceLabel } from '../src/shared/source'

describe('sourceKey — raw URL bỏ ?query và #hash', () => {
  it('bảng URL chuẩn (plan §5.1)', () => {
    expect(sourceKey('https://vnexpress.net/bai-bao?utm_source=x#top')).toBe('https://vnexpress.net/bai-bao')
    expect(sourceKey('https://vnexpress.net/bai-bao/')).toBe('https://vnexpress.net/bai-bao/') // giữ "/" cuối
    expect(sourceKey('https://www.a.vn/x?fbclid=1')).toBe('https://www.a.vn/x') // giữ www
    expect(sourceKey('https://a.vn/article?id=123')).toBe('https://a.vn/article')
    expect(sourceKey('https://a.vn/article?id=456')).toBe('https://a.vn/article') // known limitation: cùng nhóm
    expect(sourceKey('chrome://extensions')).toBeNull()
    expect(sourceKey('file:///C:/a.pdf')).toBeNull()
    expect(sourceKey(null)).toBeNull()
    expect(sourceKey('')).toBeNull()
    expect(sourceKey('   ')).toBeNull()
  })

  it('query/hash bị bỏ, path giữ nguyên, scheme http vẫn nhận', () => {
    expect(sourceKey('http://a.vn/p/a?b=1')).toBe('http://a.vn/p/a')
    expect(sourceKey('https://a.vn/p/a#frag')).toBe('https://a.vn/p/a')
    expect(sourceKey('  https://a.vn/p/a?x=1  ')).toBe('https://a.vn/p/a') // trim khoảng trắng
    expect(sourceKey('https://a.vn')).toBe('https://a.vn/') // pathname mặc định "/"
  })

  it('URL hỏng → null, không ném lỗi', () => {
    expect(sourceKey('khong-phai-url')).toBeNull()
    expect(sourceKey('https://')).toBeNull()
    expect(sourceKey('javascript:alert(1)')).toBeNull()
  })
})

describe('sourceDomain', () => {
  it('hostname giữ www, lowercase; protocol không hợp lệ → null', () => {
    expect(sourceDomain('https://WWW.A.VN/x?y=1')).toBe('www.a.vn')
    expect(sourceDomain('http://a.vn:8080/x')).toBe('a.vn')
    expect(sourceDomain('chrome://extensions')).toBeNull()
    expect(sourceDomain(null)).toBeNull()
    expect(sourceDomain('rác')).toBeNull()
  })
})

describe('sourceLabel', () => {
  it('host + path; path "/" chỉ còn host; bỏ query/hash', () => {
    expect(sourceLabel('https://vnexpress.net/bai-bao?utm=x#top')).toBe('vnexpress.net/bai-bao')
    expect(sourceLabel('https://vnexpress.net/')).toBe('vnexpress.net')
    expect(sourceLabel('https://a.vn')).toBe('a.vn')
  })

  it('decode path %20; path % hỏng → fallback không decode', () => {
    expect(sourceLabel('https://a.vn/bai%20vi%E1%BA%BFt')).toBe('a.vn/bai viết')
    expect(sourceLabel('https://a.vn/x%zz')).toBe('a.vn/x%zz')
  })

  it('cắt ngắn ở max, giữ dấu …', () => {
    const long = `https://a.vn/${'p'.repeat(120)}`
    const out = sourceLabel(long, 40)!
    expect(out).toHaveLength(40)
    expect(out.endsWith('…')).toBe(true)
    expect(sourceLabel(long, 200)).toBe(sourceKey(long)!.slice('https://'.length))
  })

  it('URL null/hỏng → null', () => {
    expect(sourceLabel(null)).toBeNull()
    expect(sourceLabel('chrome://x')).toBeNull()
  })
})

describe('groupByPage', () => {
  it('gom theo sourceKey, giữ thứ tự xuất hiện, nhóm unknown cuối', () => {
    const items = [
      { id: '1', url: 'https://a.vn/bai-1?utm=x' },
      { id: '2', url: 'https://b.vn/bai-2' },
      { id: '3', url: 'https://a.vn/bai-1#top' },
      { id: '4', url: null },
      { id: '5', url: 'chrome://x' },
    ]
    const groups = groupByPage(items)
    expect(groups.map((g) => g.label)).toEqual(['a.vn/bai-1', 'b.vn/bai-2', 'Không rõ trang'])
    expect(groups[0]!.items.map((i) => i.id)).toEqual(['1', '3'])
    expect(groups[0]!.url).toBe('https://a.vn/bai-1?utm=x') // URL gốc của item đầu
    expect(groups.at(-1)!.items.map((i) => i.id)).toEqual(['4', '5'])
    expect(groups.at(-1)!.url).toBeNull()
  })

  it('danh sách rỗng → không nhóm', () => {
    expect(groupByPage([])).toEqual([])
  })

  it('một nhóm duy nhất khi mọi URL trùng sau chuẩn hoá', () => {
    const groups = groupByPage([
      { id: '1', url: 'https://a.vn/x' },
      { id: '2', url: 'https://a.vn/x?q=2' },
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0]!.items).toHaveLength(2)
  })
})
