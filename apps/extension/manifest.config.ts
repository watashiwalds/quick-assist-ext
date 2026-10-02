import { defineManifest } from '@crxjs/vite-plugin'
import pkg from './package.json' with { type: 'json' }

// Quyền tối thiểu (SDS §8, task H01): KHÔNG có content script chạy trên mọi trang,
// KHÔNG có "<all_urls>". Đọc vùng bôi đen / hiện toast bằng chrome.scripting chỉ
// trên tab người dùng vừa thao tác (activeTab cấp quyền tạm thời).
export default defineManifest((env) => {
  const apiOrigin = new URL(process.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1').origin
  return {
    manifest_version: 3,
    name: env.mode === 'production' ? 'QuickAssist' : 'QuickAssist (dev)',
    version: pkg.version,
    description: 'Ghi chú nhanh nội dung web, tóm tắt bằng AI và tìm kiếm theo ngữ nghĩa.',
    action: { default_popup: 'src/ui/popup/index.html', default_title: 'QuickAssist' },
    side_panel: { default_path: 'src/ui/sidepanel/index.html' },
    background: { service_worker: 'src/background/index.ts', type: 'module' },
    permissions: ['contextMenus', 'storage', 'identity', 'scripting', 'activeTab', 'alarms', 'sidePanel'],
    host_permissions: [`${apiOrigin}/*`],
    commands: {
      'quick-note': {
        suggested_key: { default: 'Ctrl+Alt+N', mac: 'Command+Option+N' },
        description: 'Ghi chú nhanh đoạn đang bôi đen',
      },
    },
    content_security_policy: {
      extension_pages: "script-src 'self'; object-src 'self'",
    },
  }
})
