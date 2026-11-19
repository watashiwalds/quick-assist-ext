/**
 * Badge % tin cậy dùng chung (Phase 5 hardening — UX plan §5.5).
 *
 * Hai nơi dùng thật:
 *  - Tìm trong trang: `confidence` do LLM chấm (hoặc cosine khi AI lỗi → `verified=false`).
 *  - Kết quả tìm kiếm: `similarity` cosine của note.
 *
 * Chỉ hiển thị số + tooltip giải thích nguồn số; phần chữ cho trình đọc màn hình nằm trong
 * `.sr-only` để badge gọn nhưng vẫn có ngữ nghĩa.
 */
export function ConfidenceBadge({
  value,
  kind = 'confidence',
  verified = true,
  className,
}: {
  /** 0..1 — ngoài khoảng sẽ được kẹp lại (dữ liệu cũ/lỗi làm tròn). */
  value: number
  kind?: 'confidence' | 'similarity'
  /** `false` = AI chưa thẩm định, số là cosine fallback. */
  verified?: boolean
  className?: string
}) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  const title =
    kind === 'similarity'
      ? 'Độ tương đồng ngữ nghĩa (cosine)'
      : verified
        ? 'AI tin cậy đoạn này khớp truy vấn'
        : 'AI chưa thẩm định — theo độ tương đồng cosine'
  const label = kind === 'similarity' || !verified ? 'Độ tương đồng ' : 'Độ tin cậy '
  return (
    <span className={`confidence-badge${verified ? '' : ' is-unverified'}${className ? ` ${className}` : ''}`} title={title}>
      <span className="sr-only">{label}</span>
      {pct}%
    </span>
  )
}
