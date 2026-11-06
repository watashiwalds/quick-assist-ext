/**
 * Hỏi đáp AI trên ghi chú (X02, SDS §5.1.6): câu trả lời hiện dần từng phần, trích dẫn [n] bấm được để mở
 * ghi chú nguồn, nút Dừng giữa chừng, lọc theo thư mục, giữ tối đa 5 cặp hỏi–đáp gần nhất làm ngữ cảnh.
 */
import { type FormEvent, type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from 'react'
import type { ChatSource } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Button, EmptyState, ErrorState, Select, TextArea } from '../../components'
import { useAsync } from '../../lib/hooks'
import type { ChatMessageItem, ChatState } from './useChat'

const EXAMPLES = ['Tóm tắt những gì mình đã lưu tuần này', 'Ghi chú nào nói về cách nấu phở?', 'So sánh các ý chính trong ghi chú về Kubernetes']

export function ChatView({
  chat,
  onOpenNote,
  onGoSettings,
}: {
  chat: ChatState
  onOpenNote: (noteId: string) => void
  onGoSettings: () => void
}) {
  const [draft, setDraft] = useState('')
  const folders = useAsync(() => rpc('folders/list'), [])
  const endRef = useRef<HTMLDivElement>(null)
  const last = chat.messages.at(-1)

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' })
  }, [chat.messages.length, last?.text.length])

  function send(text = draft) {
    if (!text.trim() || chat.streaming) return
    chat.ask(text)
    setDraft('')
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    send()
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  return (
    <section className="stack chat" aria-label="Hỏi đáp với ghi chú">
      <div className="toolbar">
        <Select
          aria-label="Hỏi trong thư mục"
          value={chat.folderId ?? ''}
          disabled={chat.streaming}
          onChange={(e) => chat.setFolderId(e.target.value || null)}
        >
          <option value="">Trong mọi thư mục</option>
          {folders.data?.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </Select>
        <Button variant="ghost" size="sm" onClick={chat.reset} disabled={!chat.messages.length}>
          Cuộc trò chuyện mới
        </Button>
      </div>

      {!chat.messages.length && (
        <EmptyState title="Hỏi AI về các ghi chú bạn đã lưu">
          <p>AI chỉ trả lời dựa trên ghi chú của bạn và ghi rõ nguồn [1], [2]… để bạn kiểm tra lại.</p>
          <div className="row wrap">
            {EXAMPLES.map((q) => (
              <Button key={q} variant="ghost" size="sm" onClick={() => send(q)}>
                {q}
              </Button>
            ))}
          </div>
        </EmptyState>
      )}

      <ol className="chat-log" role="log" aria-label="Hội thoại" aria-live="off">
        {chat.messages.map((m) =>
          m.role === 'user' ? (
            <li key={m.id} className="chat-msg chat-user">
              <span className="sr-only">Bạn hỏi: </span>
              <div className="prewrap">{m.text}</div>
            </li>
          ) : (
            <AssistantMessage key={m.id} msg={m} onOpenNote={onOpenNote} onGoSettings={onGoSettings} />
          ),
        )}
      </ol>
      <div ref={endRef} />

      <p className="sr-only" aria-live="polite">
        {last?.status === 'streaming' ? 'Đang trả lời…' : last?.status === 'done' ? 'Đã trả lời xong.' : ''}
      </p>

      <form className="stack chat-input" onSubmit={onSubmit}>
        <TextArea
          aria-label="Câu hỏi về ghi chú"
          placeholder="Hỏi về ghi chú của bạn… (Enter để gửi, Shift+Enter xuống dòng)"
          rows={2}
          maxLength={2000}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="row spread">
          <small className="muted">Mỗi câu hỏi dùng hạn mức AI.</small>
          {chat.streaming ? (
            <Button type="button" variant="danger" onClick={chat.stop}>
              Dừng
            </Button>
          ) : (
            <Button type="submit" disabled={!draft.trim()}>
              Gửi
            </Button>
          )}
        </div>
      </form>
    </section>
  )
}

function AssistantMessage({
  msg,
  onOpenNote,
  onGoSettings,
}: {
  msg: ChatMessageItem
  onOpenNote: (noteId: string) => void
  onGoSettings: () => void
}) {
  const sources = msg.sources ?? []
  const cited = new Set([...msg.text.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1])))
  return (
    <li className="chat-msg chat-ai">
      <span className="sr-only">AI trả lời: </span>
      {msg.text ? (
        <div className="prewrap">{withCitations(msg.text, sources, onOpenNote)}</div>
      ) : (
        msg.status === 'streaming' && <span className="muted">Đang tìm trong ghi chú…</span>
      )}
      {msg.status === 'streaming' && msg.text && <span className="chat-caret" aria-hidden="true" />}
      {msg.status === 'stopped' && <small className="muted">(đã dừng)</small>}
      {msg.status === 'error' && msg.error && (
        <ErrorState
          error={msg.error}
          action={
            msg.error.code === 'QUOTA_EXCEEDED' ? (
              <Button variant="link" size="sm" onClick={onGoSettings}>
                Xem hạn mức
              </Button>
            ) : undefined
          }
        />
      )}
      {sources.length > 0 && (
        <details className="chat-sources" open={msg.status !== 'streaming'}>
          <summary>Nguồn ({sources.length})</summary>
          <ol className="list">
            {sources.map((s) => (
              <li key={s.chunk_id} className={cited.has(s.index) ? 'chat-source cited' : 'chat-source'}>
                <div className="row spread">
                  <strong className="grow ellipsis">
                    [{s.index}] {s.title ?? 'Ghi chú'}
                  </strong>
                </div>
                <div className="clamp muted">{s.snippet}</div>
                <div className="row actions">
                  <Button variant="ghost" size="sm" onClick={() => onOpenNote(s.note_id)}>
                    Mở ghi chú
                  </Button>
                  {s.url && (
                    <a className="btn btn-ghost btn-sm" href={s.url} target="_blank" rel="noreferrer noopener">
                      Trang nguồn ↗
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </details>
      )}
    </li>
  )
}

/** Thay "[n]" trong câu trả lời bằng nút mở ghi chú nguồn tương ứng (nếu n là nguồn có thật). */
export function withCitations(text: string, sources: ChatSource[], onOpenNote: (noteId: string) => void): ReactNode[] {
  const byIndex = new Map(sources.map((s) => [s.index, s]))
  return text.split(/(\[\d+\])/g).map((part, i) => {
    const m = /^\[(\d+)\]$/.exec(part)
    const src = m ? byIndex.get(Number(m[1])) : undefined
    if (!src) return part
    return (
      <button
        key={i}
        type="button"
        className="cite"
        title={`Mở ghi chú: ${src.title ?? 'Ghi chú'}`}
        aria-label={`Nguồn ${src.index}: ${src.title ?? 'Ghi chú'}`}
        onClick={() => onOpenNote(src.note_id)}
      >
        [{src.index}]
      </button>
    )
  })
}
