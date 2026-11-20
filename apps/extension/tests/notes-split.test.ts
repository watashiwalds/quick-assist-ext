/** Chia tài liệu dài (D2): biên đoạn → câu → từ, không mất ký tự, không vượt trần. */
import { describe, expect, it } from 'vitest'
import {
  buildNoteParts,
  estimateChunks,
  resolveSplitChars,
  splitText,
  SPLIT_PRESETS,
} from '../src/shared/notes/split'

describe('splitText', () => {
  it('nội dung ≤ trần giữ nguyên một phần', () => {
    expect(splitText('ngắn', 100)).toEqual(['ngắn'])
    expect(splitText('x'.repeat(100), 100)).toEqual(['x'.repeat(100)])
    expect(splitText('', 100)).toEqual([])
  })

  it('ưu tiên biên đoạn: mỗi phần ≤ trần và ghép lại đúng nguyên văn', () => {
    const p = 'a'.repeat(9_000)
    const text = [p, p, p].join('\n\n') // 27 004 ký tự, biên đoạn ở 9 002 và 18 004
    const parts = splitText(text, 20_000)
    expect(parts.map((x) => x.length)).toEqual([18_004, 9_000])
    expect(parts.join('')).toBe(text)
    expect(Math.max(...parts.map((x) => x.length))).toBeLessThanOrEqual(20_000)
  })

  it('không có đoạn thì cắt ở cuối câu rồi tới từ', () => {
    const sentences = `${'a'.repeat(60)}. ${'b'.repeat(60)}`
    expect(splitText(sentences, 100)).toEqual([`${'a'.repeat(60)}. `, 'b'.repeat(60)])

    const words = `${'a'.repeat(60)} ${'b'.repeat(60)}`
    expect(splitText(words, 100)).toEqual([`${'a'.repeat(60)} `, 'b'.repeat(60)])
  })

  it('không có biên nào → cắt cứng tại trần; tổng ký tự không đổi', () => {
    const text = 'w'.repeat(250)
    const parts = splitText(text, 100)
    expect(parts.map((x) => x.length)).toEqual([100, 100, 50])
    expect(parts.join('')).toBe(text)
  })

  it('văn bản hỗn hợp dài 157k: không mất chữ, không phần nào vượt trần', () => {
    const paragraph = (i: number) => `Đoạn ${i}. ` + 'nội dung tìm kiếm, câu thứ hai. '.repeat(200)
    const text = Array.from({ length: 25 }, (_, i) => paragraph(i)).join('\n\n')
    expect(text.length).toBeGreaterThan(150_000)
    const parts = splitText(text, 20_000)
    expect(parts.length).toBeGreaterThanOrEqual(8)
    expect(parts.join('')).toBe(text)
    expect(parts.every((p) => p.length > 0 && p.length <= 20_000)).toBe(true)
    // Mục tiêu 18k: các phần đều quanh 18k, không nhồi sát trần 20k.
    expect(parts.filter((p) => p.length > 18_000)).toHaveLength(1) // phần cuối có thể 18k–20k
  })
})

describe('buildNoteParts', () => {
  it('gộp các đoạn theo thứ tự bằng dòng trống rồi chia', () => {
    expect(buildNoteParts(['a', 'b', 'c'], 100)).toEqual(['a\n\nb\n\nc'])
    const parts = buildNoteParts(['x'.repeat(40), 'y'.repeat(40), 'z'.repeat(40)], 100)
    expect(parts).toEqual([`${'x'.repeat(40)}\n\n${'y'.repeat(40)}\n\n`, 'z'.repeat(40)])
    expect(buildNoteParts(['w'.repeat(250)], 100).map((p) => p.length)).toEqual([100, 100, 50])
  })
})

describe('resolveSplitChars + estimateChunks', () => {
  it('preset không vượt trần server và luôn có giá trị hợp lệ', () => {
    expect(SPLIT_PRESETS).toEqual([8_000, 12_000, 16_000, 18_000, 20_000])
    expect(resolveSplitChars(12_000)).toBe(12_000)
    expect(resolveSplitChars(25_000)).toBe(20_000)
    expect(resolveSplitChars(undefined)).toBe(20_000)
    expect(resolveSplitChars(0)).toBe(1_000)
  })

  it('ước lượng chunk theo ~1 200 ký tự (157k ≈ 131 chunk)', () => {
    expect(estimateChunks(0)).toBe(1)
    expect(estimateChunks(1_200)).toBe(1)
    expect(estimateChunks(1_201)).toBe(2)
    expect(estimateChunks(156_885)).toBe(131)
  })
})
