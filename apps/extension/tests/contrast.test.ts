/** A05 — token màu đạt WCAG 2.1 AA (≥ 4.5:1 chữ thường, ≥ 3:1 thành phần giao diện) ở cả sáng & tối. */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(__dirname, '../src/ui/styles.css'), 'utf8')

function tokens(block: string): Record<string, string> {
  return Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1]!, m[2]!]))
}
const light = tokens(css.slice(css.indexOf(':root {'), css.indexOf('@media (prefers-color-scheme: dark)')))
const dark = { ...light, ...tokens(css.slice(css.indexOf('@media (prefers-color-scheme: dark)'), css.indexOf('* {'))) }

function lum(hex: string): number {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0]! + 0.7152 * c[1]! + 0.0722 * c[2]!
}
export function contrast(a: string, b: string): number {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p) as [number, number]
  return (x + 0.05) / (y + 0.05)
}

// [chữ, nền, ngưỡng]
const PAIRS: Array<[string, string, number]> = [
  ['fg', 'bg', 4.5], ['muted', 'bg', 4.5], ['muted', 'surface', 4.5], ['accent', 'bg', 4.5],
  ['accent-fg', 'accent', 4.5], ['ok', 'bg', 4.5], ['warn', 'bg', 4.5], ['danger', 'bg', 4.5],
  ['fg', 'warn-bg', 4.5], ['fg', 'info-bg', 4.5], ['fg', 'danger-bg', 4.5], ['fg', 'ok-bg', 4.5],
  ['bg', 'fg', 4.5], ['danger-fg', 'danger', 4.5], ['border', 'bg', 1.2], ['focus', 'bg', 3],
]

describe('độ tương phản token (WCAG AA)', () => {
  it('khớp chuẩn RFC (đen/trắng = 21:1)', () => expect(contrast('#000000', '#ffffff')).toBeCloseTo(21, 0))
  for (const [name, t] of [['sáng', light], ['tối', dark]] as const) {
    for (const [fg, bg, min] of PAIRS) {
      it(`${name}: --${fg} trên --${bg} ≥ ${min}`, () => {
        expect(t[fg], fg).toBeDefined()
        expect(contrast(t[fg]!, t[bg]!)).toBeGreaterThanOrEqual(min)
      })
    }
  }
  it('không còn mã màu cứng #fff/#ffffff trong quy tắc CSS (chỉ dùng token)', () => {
    const rules = css.slice(css.indexOf('* {'))
    expect(rules.match(/color:\s*#fff\b/g) ?? []).toEqual([])
  })
})
