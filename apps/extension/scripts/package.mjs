// H06 — đóng gói bản phát hành: build production → rà soát bundle (H01) → release/quickassist-<version>.zip
//   VITE_API_BASE_URL=https://api.<domain>/api/v1 VITE_GOOGLE_CLIENT_ID=... VITE_EXTENSION_KEY=... npm run package
// Tệp zip dùng để cài thủ công (Load unpacked sau khi giải nén) hoặc tải lên Chrome Web Store.
import { execSync } from 'node:child_process'
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { deflateRawSync } from 'node:zlib'

const root = join(import.meta.dirname, '..')
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))
if (!process.env.VITE_API_BASE_URL?.startsWith('https://') && !process.argv.includes('--allow-http')) {
  console.error('❌ VITE_API_BASE_URL phải là https:// cho bản phát hành (thêm --allow-http để thử cục bộ)')
  process.exit(1)
}
if (!process.env.VITE_GOOGLE_CLIENT_ID) console.warn('⚠ thiếu VITE_GOOGLE_CLIENT_ID — đăng nhập Google sẽ không hoạt động')
execSync('npm run build', { cwd: root, stdio: 'inherit' })
execSync('node scripts/check-bundle.mjs dist', { cwd: root, stdio: 'inherit' })

// --- zip tối giản (deflate) không cần thư viện ngoài ---
const CRC = new Uint32Array(256).map((_, n) => {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  return c >>> 0
})
const crc32 = (buf) => {
  let c = 0xffffffff
  for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}
const walk = (d) => readdirSync(d).flatMap((f) => (statSync(join(d, f)).isDirectory() ? walk(join(d, f)) : [join(d, f)]))
const dist = join(root, 'dist')
const local = []
const central = []
let offset = 0
for (const file of walk(dist).sort()) {
  const name = Buffer.from(relative(dist, file).replaceAll('\\', '/'))
  const data = readFileSync(file)
  const comp = deflateRawSync(data, { level: 9 })
  const crc = crc32(data)
  const h = Buffer.alloc(30)
  h.writeUInt32LE(0x04034b50, 0); h.writeUInt16LE(20, 4); h.writeUInt16LE(0x0800, 6); h.writeUInt16LE(8, 8)
  h.writeUInt32LE(crc, 14); h.writeUInt32LE(comp.length, 18); h.writeUInt32LE(data.length, 22); h.writeUInt16LE(name.length, 26)
  local.push(h, name, comp)
  const c = Buffer.alloc(46)
  c.writeUInt32LE(0x02014b50, 0); c.writeUInt16LE(20, 4); c.writeUInt16LE(20, 6); c.writeUInt16LE(0x0800, 8); c.writeUInt16LE(8, 10)
  c.writeUInt32LE(crc, 16); c.writeUInt32LE(comp.length, 20); c.writeUInt32LE(data.length, 24); c.writeUInt16LE(name.length, 28)
  c.writeUInt32LE(offset, 42)
  central.push(c, name)
  offset += 30 + name.length + comp.length
}
const cd = Buffer.concat(central)
const end = Buffer.alloc(22)
end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(central.length / 2, 8); end.writeUInt16LE(central.length / 2, 10)
end.writeUInt32LE(cd.length, 12); end.writeUInt32LE(offset, 16)
mkdirSync(join(root, 'release'), { recursive: true })
const out = join(root, 'release', `quickassist-${pkg.version}.zip`)
writeFileSync(out, Buffer.concat([...local, cd, end]))
console.log(`✅ ${relative(root, out)} (${(statSync(out).size / 1024).toFixed(0)} KB, ${central.length / 2} tệp)`)
