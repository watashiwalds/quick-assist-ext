/**
 * Chia tài liệu dài thành các phần ≤ trần một ghi chú (D2 — tài liệu nhiều part).
 *
 * Quy tắc: ưu tiên ranh giới ĐOẠN (`\n\n`) → CÂU (`.!?…` + khoảng trắng) → TỪ (khoảng trắng),
 * cuối cùng mới cắt cứng. Không bỏ ký tự nào: `splitText(text).join('') === text`
 * (backend `strip()` hai đầu mỗi part nên khoảng trắng ở mép có thể mất — nội dung thì không).
 *
 * Mục tiêu mỗi phần ≈ 90% trần (mặc định 18k với trần 20k) để không sát giới hạn server;
 * không phần nào vượt trần. Hàm thuần, không I/O → dùng chung UI/background và test độc lập.
 */
import { config } from '../config'

/** Ngưỡng chia cho người dùng chọn trong Cài đặt (không bao giờ vượt trần server). */
export const SPLIT_PRESETS = [8_000, 12_000, 16_000, 18_000, 20_000] as const

/** Mục tiêu mỗi phần = 90% ngưỡng chia. */
export const TARGET_RATIO = 0.9

/** Trần chia hợp lệ: preset đã chọn nhưng ≤ MAX_NOTE_CHARS của server. */
export function resolveSplitChars(value: number | null | undefined): number {
  const n = typeof value === 'number' && Number.isFinite(value) ? Math.floor(value) : config.maxNoteChars
  return Math.min(config.maxNoteChars, Math.max(1_000, n))
}

/** Số chunk ước tính khi tạo chỉ mục (backend chia ~1 200 ký tự/chunk). */
export function estimateChunks(chars: number, chunkChars = 1_200): number {
  return Math.max(1, Math.ceil(Math.max(0, chars) / chunkChars))
}

/** Cắt sau `\n\n` gần cuối đoạn trong khoảng [from, to], sau đó là câu rồi tới từ. */
function paragraphCut(text: string, from: number, to: number): number | null {
  const at = text.lastIndexOf('\n\n', to)
  return at >= from ? at + 2 : null
}

const SENTENCE = /[.!?…](?:["'”’)\]]+)?\s+/g

function sentenceCut(text: string, from: number, to: number): number | null {
  const slice = text.slice(0, to)
  let best: number | null = null
  for (const m of slice.matchAll(SENTENCE)) {
    const end = (m.index ?? 0) + m[0].length
    if (end >= from) best = end
  }
  return best
}

function wordCut(text: string, from: number, to: number): number | null {
  const at = text.lastIndexOf(' ', to)
  return at >= from ? at + 1 : null
}

/**
 * Chọn điểm cắt cho phần đầu: boundary ưu tiên cao nhất rơi vào khoảng [~60% target, target],
 * nếu không có thì nới tới trần. Không có boundary nào → cắt cứng tại trần.
 */
function chooseCut(text: string, maxChars: number, targetChars: number): number {
  const minCut = Math.max(1, Math.floor(targetChars * 0.6))
  for (const find of [paragraphCut, sentenceCut, wordCut]) {
    const cut = find(text, minCut, targetChars) ?? find(text, minCut, maxChars)
    if (cut !== null) return Math.min(cut, maxChars)
  }
  return maxChars
}

/** Chia `text` thành các phần ≤ `maxChars` (mặc định trần server), ưu tiên biên đoạn/câu/từ. */
export function splitText(
  text: string,
  maxChars: number = config.maxNoteChars,
  targetChars: number = Math.floor(maxChars * TARGET_RATIO),
): string[] {
  const max = Math.max(1, Math.floor(maxChars))
  const target = Math.min(max, Math.max(1, Math.floor(targetChars)))
  if (!text) return []
  if (text.length <= max) return [text]

  const parts: string[] = []
  let rest = text
  while (rest.length > max) {
    const cut = chooseCut(rest, max, target)
    parts.push(rest.slice(0, cut))
    rest = rest.slice(cut)
  }
  if (rest) parts.push(rest)
  return parts
}

/** Gộp các đoạn rời (giữ thứ tự, cách nhau dòng trống) rồi chia thành part ≤ ngưỡng. */
export function buildNoteParts(texts: string[], maxChars: number = config.maxNoteChars): string[] {
  return splitText(texts.join('\n\n'), maxChars)
}
