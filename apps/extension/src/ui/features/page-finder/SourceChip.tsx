/**
 * SourceChip — nguồn tham chiếu cho nội dung dán (ADR-0018): chip hiển thị URL + tiêu đề tab
 * đang mở, cho phép "Lấy lại tab", "Bỏ" hoặc nhập URL tay. Nguồn tham chiếu CHỈ để mở lại bài
 * và gom nhóm — không khẳng định văn bản được copy từ tab đó, nên luôn sửa/bỏ được.
 */
import { useState } from 'react'
import { sourceLabel, type SourceRef } from '@/shared/source'
import { Button, Icon } from '../../components'

const MAX_URL_CHARS = 2048

export function SourceChip({
  source,
  onCapture,
  onClear,
  onManual,
}: {
  source: SourceRef | null
  /** Lấy lại tab hiện tại (ghi đè nguồn hiện có). */
  onCapture: () => void
  /** Bỏ nguồn — quét/lưu sẽ không kèm URL. */
  onClear: () => void
  /** Dùng URL nhập tay; trả về false nếu URL không hợp lệ (http/https). */
  onManual: (url: string) => boolean
}) {
  const [editing, setEditing] = useState(false)
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)

  const submitManual = () => {
    const trimmed = url.trim()
    if (onManual(trimmed)) {
      setEditing(false)
      setUrl('')
      setError(null)
    } else {
      setError('URL phải bắt đầu bằng http:// hoặc https://')
    }
  }

  return (
    <div className="paste-source" aria-label="Nguồn tham chiếu">
      {source ? (
        <>
          <div className="paste-source-info">
            <Icon name="external" size={13} aria-hidden="true" />
            <div className="paste-source-text">
              <span className="paste-source-title" title={source.title || source.url}>
                {source.title || sourceLabel(source.url) || source.url}
              </span>
              <a className="paste-source-url" href={source.url} target="_blank" rel="noreferrer noopener" title={`Mở trang nguồn: ${source.url}`}>
                {sourceLabel(source.url) ?? source.url}
              </a>
            </div>
          </div>
          <div className="paste-source-actions">
            <Button variant="quiet" size="sm" onClick={onCapture} title="Lấy lại URL và tiêu đề tab đang mở">
              Lấy lại tab
            </Button>
            <Button variant="quiet" size="sm" onClick={() => setEditing((v) => !v)}>
              Nhập URL
            </Button>
            <Button variant="quiet" size="sm" onClick={onClear} title="Bỏ nguồn tham chiếu — ghi chú sẽ lưu không kèm URL">
              Bỏ
            </Button>
          </div>
        </>
      ) : (
        <>
          <span className="paste-source-empty">Chưa gắn nguồn.</span>
          <div className="paste-source-actions">
            <Button variant="quiet" size="sm" onClick={onCapture} title="Dùng tab đang mở làm nguồn tham chiếu">
              <Icon name="clipboard" size={13} />
              Lấy từ tab hiện tại
            </Button>
            <Button variant="quiet" size="sm" onClick={() => setEditing((v) => !v)}>
              Nhập URL
            </Button>
          </div>
        </>
      )}
      {editing && (
        <div className="paste-source-manual">
          <div className="paste-source-manual-row">
            <input
              type="url"
              value={url}
              maxLength={MAX_URL_CHARS}
              placeholder="https://…"
              aria-label="URL nguồn tham chiếu"
              aria-invalid={!!error || undefined}
              onChange={(e) => {
                setUrl(e.target.value)
                setError(null)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  submitManual()
                }
              }}
            />
            <Button size="sm" onClick={submitManual} disabled={!url.trim()}>
              Dùng URL
            </Button>
          </div>
          {error && (
            <p className="paste-source-error" role="alert">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
