/**
 * Tổng hợp kết quả tìm kiếm dùng chung cho Thư viện và tab Tìm kiếm (Phase 5 hardening).
 *
 * `notes` chỉ chứa tối đa 10 note/nguồn mà API trả về; `note_count` mới là tổng số ghi chú
 * đạt ngưỡng trong nguồn. Đếm theo `notes` sẽ báo thiếu khi một nguồn có hơn 10 ghi chú khớp.
 */
import type { SearchSource } from '@/shared/api/types'

export function countSearchNotes(sources: SearchSource[]): number {
  return sources.reduce((total, source) => total + source.note_count, 0)
}
