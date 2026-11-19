/**
 * Nguồn của câu trả lời Hỏi AI (Phase 4 — UX plan §5.4.4; tách riêng Phase 5 hardening).
 *
 * Chip và "Chi tiết nguồn" nhóm theo DOMAIN (`source_index`/`source_domain` do backend gắn),
 * trong khi trích dẫn `[n]` vẫn theo note để bấm mở đúng ghi chú. Tách khỏi ChatView để
 * `groupChatSources` test được độc lập và ChatView bớt ôm đồ thị UI.
 */
import type { ChatSource } from '@/shared/api/types'
import { Button, Icon } from '../../components'

/** Một nhóm nguồn = một domain (hoặc "Không rõ nguồn"); `notes` giữ thứ tự trích dẫn gốc. */
export interface ChatSourceGroup {
  key: string
  domain: string | null
  label: string
  notes: ChatSource[]
}

/**
 * Nhóm nguồn theo domain. Key ưu tiên `source_index` do backend gắn theo hạng nguồn; hội thoại
 * cũ lưu trước Phase 1 chưa có trường này thì lọt về nhóm theo `source_domain`. Mỗi nguồn thuộc
 * đúng một nhóm (không trùng giữa các nhóm); "Không rõ nguồn" luôn cuối như xếp hạng nguồn ở
 * Thư viện.
 */
export function groupChatSources(sources: ChatSource[]): ChatSourceGroup[] {
  const groups = new Map<string, ChatSourceGroup>()
  for (const s of sources) {
    const domain = s.source_domain ?? null
    const key = typeof s.source_index === 'number' ? `r${s.source_index}` : `d${domain ?? ''}`
    let group = groups.get(key)
    if (!group) {
      group = { key, domain, label: domain ?? 'Không rõ nguồn', notes: [] }
      groups.set(key, group)
    }
    group.notes.push(s)
  }
  const listed = [...groups.values()]
  return [...listed.filter((g) => g.domain !== null), ...listed.filter((g) => g.domain === null)]
}

/** Chip nguồn nhóm theo domain + `Chi tiết nguồn` nhóm theo domain (khoá đến khi câu trả lời xong
 * vì snippet có thể chưa sẵn sàng). Trích dẫn `[n]` vẫn theo note để mở đúng ghi chú. */
export function Sources({
  sources,
  cited,
  streaming,
  onOpenNote,
}: {
  sources: ChatSource[]
  cited: Set<number>
  streaming: boolean
  onOpenNote: (noteId: string) => void
}) {
  const titleOf = (s: ChatSource) => s.title ?? 'Ghi chú'
  const groups = groupChatSources(sources)
  return (
    <div className="sources">
      <div className="source-row">
        <span className="source-label">Nguồn ({groups.length})</span>
        <div className="source-chips">
          {groups.map((g) => (
            <span key={g.key} className="source-cluster">
              <span className="source-cluster-label" title={g.label}>
                {g.label}
              </span>
              {g.notes.map((s) => (
                <button
                  key={s.chunk_id}
                  type="button"
                  className={`source-chip${cited.has(s.index) ? ' is-cited' : ''}`}
                  title={titleOf(s)}
                  aria-label={`Nguồn ${s.index}: ${titleOf(s)}`}
                  onClick={() => onOpenNote(s.note_id)}
                >
                  <span className="chip-index">[{s.index}]</span>
                  <span className="chip-title">{titleOf(s)}</span>
                </button>
              ))}
            </span>
          ))}
        </div>
      </div>

      {streaming ? (
        <p className="source-pending">Nguồn đã sẵn sàng — chi tiết mở khi câu trả lời hoàn tất.</p>
      ) : (
        <details className="source-more">
          <summary>
            <Icon name="chevron-right" size={11} />
            Chi tiết nguồn
          </summary>
          <ul className="source-groups">
            {groups.map((g) => (
              <li key={g.key} className="source-group-block">
                <p className="source-domain-head">
                  <span className="source-domain-name">{g.label}</span>
                  <span className="source-domain-count">
                    {new Set(g.notes.map((s) => s.note_id)).size} ghi chú
                  </span>
                </p>
                <ul className="source-cards">
                  {g.notes.map((s) => (
                    <li key={s.chunk_id} className="source-card">
                      <span className="source-index" aria-hidden="true">
                        [{s.index}]
                      </span>
                      <div className="source-body">
                        <p className="source-title">{titleOf(s)}</p>
                        <p className="source-snippet">{s.snippet}</p>
                        <div className="source-actions">
                          <Button variant="quiet" size="sm" onClick={() => onOpenNote(s.note_id)}>
                            Mở ghi chú
                          </Button>
                          {s.url && (
                            <a className="link-quiet" href={s.url} target="_blank" rel="noreferrer noopener">
                              Trang nguồn
                              <Icon name="external" size={11} />
                            </a>
                          )}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
