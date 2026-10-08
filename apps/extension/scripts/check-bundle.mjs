// H01 — rà soát bản build trước khi phát hành: không secret, không quyền thừa, không hook kiểm thử.
//   node scripts/check-bundle.mjs dist        (CI chạy sau npm run build)
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const dir = process.argv[2] ?? 'dist'
const problems = []
const files = (d) => readdirSync(d).flatMap((f) => (statSync(join(d, f)).isDirectory() ? files(join(d, f)) : [join(d, f)]))

const manifest = JSON.parse(readFileSync(join(dir, 'manifest.json'), 'utf8'))
const perms = [...(manifest.permissions ?? []), ...(manifest.host_permissions ?? [])]
if (perms.some((p) => p === '<all_urls>' || p.startsWith('*://*') || p === 'http://*/*' || p === 'https://*/*')) problems.push(`quyền host quá rộng: ${perms.join(', ')}`)
if (manifest.content_scripts?.length) problems.push('có content_scripts thường trực (chỉ được dùng activeTab + scripting)')
for (const p of ['tabs', 'history', 'cookies', 'webRequest', 'downloads', 'debugger']) if (perms.includes(p)) problems.push(`quyền không cần thiết: ${p}`)
if (!/script-src 'self'/.test(manifest.content_security_policy?.extension_pages ?? '')) problems.push('thiếu CSP extension_pages')
if ((manifest.host_permissions ?? []).some((h) => h.startsWith('http://127.0.0.1'))) problems.push('quyền trang thử E2E lọt vào bản phát hành')

const SECRET = [
  [/sk-[A-Za-z0-9_-]{20,}/, 'khoá OpenAI'],
  [/GOCSPX-[A-Za-z0-9_-]{10,}/, 'Google client_secret'],
  [/-----BEGIN [A-Z ]*PRIVATE KEY-----/, 'private key'],
  [/client_secret/i, 'chuỗi client_secret'],
  [/__qaE2E|\/auth\/dev-login/, 'hook/đăng nhập kiểm thử E2E'],
  [/\beval\(|new Function\(/, 'eval/new Function'],
]
for (const f of files(dir)) {
  if (!/\.(js|html|json|css)$/.test(f)) continue
  const text = readFileSync(f, 'utf8')
  for (const [re, what] of SECRET) if (re.test(text)) problems.push(`${what} trong ${f}`)
}
if (problems.length) {
  console.error('❌ Bundle KHÔNG đạt rà soát bảo mật:\n - ' + problems.join('\n - '))
  process.exit(1)
}
console.log(`✅ Bundle đạt rà soát (${files(dir).length} tệp; quyền: ${perms.join(', ')})`)
