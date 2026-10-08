import { defineManifest } from '@crxjs/vite-plugin'
import pkg from './package.json' with { type: 'json' }

// Quyền tối thiểu (SDS §8, task H01): KHÔNG có content script chạy trên mọi trang,
// KHÔNG có "<all_urls>". Đọc vùng bôi đen / hiện toast bằng chrome.scripting chỉ
// trên tab người dùng vừa thao tác (activeTab cấp quyền tạm thời).
export default defineManifest((env) => {
  const apiOrigin = new URL(process.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1').origin
  const e2e = process.env.VITE_E2E === 'true'
  // Khoá công khai cố định → Extension ID không đổi giữa các máy dev (R-03): redirect URI
  // OAuth và CORS_ORIGINS chỉ cần khai báo một lần. Sinh khoá: xem apps/extension/README.md.
  const key = process.env.VITE_EXTENSION_KEY?.trim()
  return {
    manifest_version: 3,
    name: env.mode === 'production' ? 'QuickAssist' : 'QuickAssist (dev)',
    version: pkg.version,
    description: 'Ghi chú nhanh nội dung web, tóm tắt bằng AI và tìm kiếm theo ngữ nghĩa.',
    ...(key ? { key } : {}),
    action: { default_popup: 'src/ui/popup/index.html', default_title: 'QuickAssist' },
    side_panel: { default_path: 'src/ui/sidepanel/index.html' },
    background: { service_worker: 'src/background/index.ts', type: 'module' },
    permissions: ['contextMenus', 'storage', 'identity', 'scripting', 'activeTab', 'alarms', 'sidePanel'],
    // Bản E2E cần thêm quyền vào trang thử nghiệm cục bộ (Playwright không tạo được user gesture
    // để cấp activeTab). Bản phát hành chỉ có origin của API.
    host_permissions: [`${apiOrigin}/*`, ...(e2e ? ['http://127.0.0.1/*'] : [])],
    commands: {
      'quick-note': {
        // Chrome KHÔNG cho phép tổ hợp Ctrl+Alt (trùng AltGr) — manifest có Ctrl+Alt sẽ khiến extension
        // không nạp được. Người dùng đổi phím ở chrome://extensions/shortcuts.
        suggested_key: { default: 'Alt+Shift+N', mac: 'Alt+Shift+N' },
        description: 'Ghi chú nhanh đoạn đang bôi đen',
      },
    },
    content_security_policy: {
      extension_pages: "script-src 'self'; object-src 'self'",
    },
    minimum_chrome_version: '116',
  }
})
