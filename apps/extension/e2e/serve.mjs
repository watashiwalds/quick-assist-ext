// Máy chủ tĩnh cho trang thử nghiệm E2E (http://127.0.0.1:4173).
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { join, normalize } from 'node:path'

const root = join(import.meta.dirname, 'pages')
createServer(async (req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^([/\\])+/, '')
  try {
    const body = await readFile(join(root, path || 'article.html'))
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(body)
  } catch {
    res.writeHead(404).end('not found')
  }
}).listen(4173, '127.0.0.1', () => console.log('e2e pages on http://127.0.0.1:4173'))
