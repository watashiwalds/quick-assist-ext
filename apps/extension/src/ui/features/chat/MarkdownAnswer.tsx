/**
 * Render câu trả lời AI dạng Markdown (X02) — react-markdown + remark-gfm.
 *
 * - An toàn mặc định: HTML thô trong câu trả lời bị bỏ qua (không dùng rehype-raw); URL link
 *   đi qua `defaultUrlTransform` nên scheme lạ (`javascript:`…) bị gỡ href trước khi render.
 * - Trích dẫn `[n]` vẫn bấm được: rehype plugin biến text node chứa `[n]` thành `<button>`
 *   khi `n` trùng một nguồn thật; code block / inline code giữ nguyên chữ. `[n]` không có
 *   nguồn tương ứng giữ nguyên text (AI có thể tự đánh số khác danh sách nguồn).
 * - `memo` + plugin identity ổn định: chỉ câu trả lời đang stream đổi text, các câu cũ
 *   không bị parse lại mỗi delta.
 */
import { memo, useMemo } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ElementContent, Root, RootContent } from 'hast'
import type { PluggableList } from 'unified'
import type { ChatSource } from '@/shared/api/types'

/** Thuộc tính đánh dấu nút trích dẫn do plugin chèn, map sang prop `data-cite`. */
const CITE_ATTR = 'data-cite'
const CITE_RE = /\[(\d+)\]/g

interface CitationOptions {
  /** Số nguồn có thật trong câu trả lời — chỉ số này được biến thành nút bấm. */
  indices: ReadonlySet<number>
}

/**
 * Tách một text node thành các node con: text thuần + `<button data-cite="n">` cho trích dẫn
 * trùng nguồn. Xuất để unit-test trực tiếp không cần react-markdown.
 */
export function splitCiteText(value: string, indices: ReadonlySet<number>): ElementContent[] {
  const out: ElementContent[] = []
  let last = 0
  for (const m of value.matchAll(CITE_RE)) {
    const index = Number(m[1])
    const at = m.index ?? 0
    if (at > last) out.push({ type: 'text', value: value.slice(last, at) })
    if (indices.has(index)) {
      out.push({
        type: 'element',
        tagName: 'button',
        properties: { [CITE_ATTR]: String(index) },
        children: [{ type: 'text', value: `[${index}]` }],
      })
    } else {
      out.push({ type: 'text', value: m[0] })
    }
    last = at + m[0].length
  }
  if (last < value.length) out.push({ type: 'text', value: value.slice(last) })
  return out
}

/**
 * Rehype plugin: đi cây hast, thay `[n]` trong text bằng nút trích dẫn; bỏ qua `code`/`pre`
 * để đoạn code hiển thị nguyên vẹn. Chỉ plugin này tạo `<button>` trong câu trả lời (HTML thô
 * bị bỏ qua) nên override `button` ở `components` không đụng nội dung AI viết.
 */
export function rehypeCitations(options?: Partial<CitationOptions>) {
  const indices = options?.indices ?? new Set<number>()
  return (tree: Root): void => {
    const visit = (parent: { children: RootContent[] }): void => {
      const next: RootContent[] = []
      for (const child of parent.children) {
        if (child.type === 'text') {
          next.push(...splitCiteText(child.value, indices))
          continue
        }
        if (child.type === 'element' && child.tagName !== 'code' && child.tagName !== 'pre') visit(child)
        next.push(child)
      }
      parent.children = next
    }
    visit(tree)
  }
}

interface MarkdownAnswerProps {
  text: string
  sources: ChatSource[]
  onOpenNote: (noteId: string) => void
}

/** Câu trả lời AI render Markdown; dùng trong `.ai-bubble` thay cho text thuần `.prewrap`. */
export const MarkdownAnswer = memo(function MarkdownAnswer({ text, sources, onOpenNote }: MarkdownAnswerProps) {
  const indices = useMemo(() => new Set(sources.map((s) => s.index)), [sources])
  const remarkPlugins = useMemo(() => [remarkGfm], [])
  const rehypePlugins = useMemo<PluggableList>(() => [[rehypeCitations, { indices }]], [indices])

  const components = useMemo<Components>(
    () => ({
      // Link ngoài mở tab mới; href đã qua defaultUrlTransform (scheme nguy hiểm bị gỡ).
      a: ({ node: _node, children, ...rest }) => (
        <a {...rest} target="_blank" rel="noreferrer noopener">
          {children}
        </a>
      ),
      // Nút trích dẫn `[n]` — cùng hành vi/tên aria với chip nguồn để test & screen reader thống nhất.
      button: ({ node, children, ...rest }) => {
        const index = Number(String(node?.properties?.[CITE_ATTR] ?? NaN))
        const source = sources.find((s) => s.index === index)
        if (!source) return <button type="button" {...rest}>{children}</button>
        const title = source.title ?? 'Ghi chú'
        return (
          <button
            type="button"
            className="cite"
            title={`Mở ghi chú: ${title}`}
            aria-label={`Mở ghi chú nguồn ${source.index}: ${title}`}
            onClick={() => onOpenNote(source.note_id)}
          >
            {children}
          </button>
        )
      },
    }),
    [sources, onOpenNote],
  )

  return (
    <div className="ai-text">
      <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  )
})
