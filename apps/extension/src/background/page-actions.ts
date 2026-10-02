/** Tương tác với trang qua chrome.scripting (cần activeTab từ thao tác của người dùng). */
import { type PageSelection, readSelection, renderToast, type ToastSpec } from '@/content/injected'

export async function getSelection(tabId: number): Promise<PageSelection | null> {
  try {
    const [res] = await chrome.scripting.executeScript({ target: { tabId }, func: readSelection })
    return (res?.result as PageSelection | undefined) ?? null
  } catch {
    return null // trang chrome://, Web Store... không cho tiêm script
  }
}

export async function showToast(tabId: number, spec: ToastSpec): Promise<void> {
  try {
    await chrome.scripting.executeScript({ target: { tabId }, func: renderToast, args: [spec] })
  } catch {
    // Không hiện được toast trên trang đặc biệt → bỏ qua, ghi chú vẫn được lưu.
  }
}
