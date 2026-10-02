/// <reference types="vitest/config" />
import { crx } from '@crxjs/vite-plugin'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import manifest from './manifest.config.ts'

export default defineConfig(({ mode }) => {
  Object.assign(process.env, loadEnv(mode, process.cwd(), 'VITE_'))
  return {
    plugins: [react(), crx({ manifest })],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    build: { target: 'es2022', sourcemap: mode !== 'production' },
    server: { port: 5173, strictPort: true, hmr: { port: 5173 } },
    test: { environment: 'node', include: ['tests/**/*.test.ts'] },
  }
})
