// Build bản E2E (dist-e2e/) — chạy được trên Windows/macOS/Linux (không dùng cú pháp biến môi trường của shell).
import { build } from 'vite'

process.env.VITE_E2E = 'true'
process.env.VITE_API_BASE_URL = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000/api/v1'
await build({ build: { outDir: 'dist-e2e', emptyOutDir: true }, logLevel: 'warn' })
console.log(`✓ dist-e2e (API ${process.env.VITE_API_BASE_URL})`)
