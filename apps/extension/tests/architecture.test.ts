/**
 * Luật phân tầng extension — chạy trong CI (giống tests/architecture ở backend).
 *  - ui/            KHÔNG import background/, shared/storage/, shared/api/* (trừ api/types) → chỉ nói chuyện qua RPC
 *  - content/        KHÔNG import gì cả (hàm được tiêm phải tự chứa)
 *  - shared/         KHÔNG import background/, ui/, content/
 *  - background/     KHÔNG import ui/
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

const SRC = join(__dirname, '..', 'src')

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f)
    return statSync(p).isDirectory() ? files(p) : /\.(ts|tsx)$/.test(f) && !f.endsWith('.d.ts') ? [p] : []
  })
}

function imports(file: string): string[] {
  const src = readFileSync(file, 'utf8')
  return [...src.matchAll(/^\s*import\s[^'"]*?['"]([^'"]+)['"]/gm)].map((m) => m[1]!)
}

function layerOf(spec: string, from: string): string | null {
  let p = spec
  if (p.startsWith('@/')) p = p.slice(2)
  else if (p.startsWith('.')) p = relative(SRC, join(from, '..', p)).replace(/\\/g, '/')
  else return null // thư viện ngoài
  return p
}

const RULES: Array<[string, RegExp, string]> = [
  ['ui/', /^(background\/|shared\/storage\/|shared\/api\/(?!types$))/, 'UI chỉ gọi background qua shared/messaging (được dùng type)'],
  ['content/', /^(background|ui|shared)\//, 'content/ phải tự chứa (được tiêm vào trang)'],
  ['shared/', /^(background|ui|content)\//, 'shared/ không phụ thuộc tầng trên'],
  ['background/', /^ui\//, 'background không import UI'],
]

describe('ranh giới kiến trúc extension', () => {
  for (const [layer, forbidden, why] of RULES) {
    it(`${layer}: ${why}`, () => {
      const bad: string[] = []
      for (const f of files(join(SRC, layer))) {
        for (const spec of imports(f)) {
          const target = layerOf(spec, f)
          if (target && forbidden.test(target)) bad.push(`${relative(SRC, f)} -> ${spec}`)
        }
      }
      expect(bad).toEqual([])
    })
  }
})
