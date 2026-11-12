/**
 * AutoChunk — "Tìm trong trang": mô tả điều cần tìm → quét trang đang xem (hoặc nội dung dán vào) →
 * chọn các đoạn AI tìm ra → lưu thành MỘT ghi chú gộp (cách ghi chú thứ hai, song song với bôi đen).
 * Xem ADR-0013 và ADR-0015 (nguồn text dán).
 *
 * Bố cục split-view (demo upgrade-plan/redesign, nhất quán Thư viện W03): rail truy vấn cố định bên trái
 * (headline + trạng thái trang + composer neo đáy), vùng kết quả bên phải (banner → tiêu đề + thao tác
 * chọn → danh sách đoạn → thanh lưu dính đáy). ≤720px: composer lên trên, kết quả cuộn chung dưới.
 *
 * Luồng: nhập truy vấn → "Đang đọc trang…" (chỉ nguồn trang) → "Đang phân tích & thẩm định…" → danh sách
 * đoạn (đã xác nhận được tích sẵn) → "Xem trên trang" cuộn + làm nổi bật → "Lưu lựa chọn" (hoặc "Lưu toàn
 * bộ" khi gần như cả trang khớp). Nguồn dán không có trang gốc nên "Xem trên trang" bị khoá và ghi chú
 * lưu không kèm URL. Không tự lưu khi người dùng chưa bấm.
 */
import { type FormEvent, type KeyboardEvent, useEffect, useId, useMemo, useState } from 'react'
import type { Folder, PageMatchItem } from '@/shared/api/types'
import { config } from '@/shared/config'
import { type SerializedError, toSerialized } from '@/shared/errors'
import { rpc } from '@/shared/messaging/client'
import type { PageMatchRun } from '@/shared/messaging/protocol'
import { Banner, Button, ConfirmDialog, EmptyState, ErrorState, Icon, Select, Spinner, TextArea, useToast } from '../../components'
import { useBroadcast } from '../../lib/hooks'

const SEP = '\n\n'
/** Ngưỡng hỏi lại trước khi lưu (ký tự) — nội dung lớn tốn hạn mức AI khi tạo chỉ mục tìm kiếm. */
const CONFIRM_CHARS = 8_000

/**
 * Gộp các đoạn (theo thứ tự trang) thành nội dung ghi chú, tách thành nhiều phần nếu vượt giới hạn
 * một ghi chú — cắt theo biên đoạn, đoạn quá dài thì cắt cứng (hiếm: đoạn ≤ 1 200 ký tự từ backend).
 */
export function buildNoteParts(texts: string[], maxChars: number = config.maxNoteChars): string[] {
  const parts: string[] = []
  let cur = ''
  for (const raw of texts) {
    for (let t = raw; t.length > 0; t = t.slice(maxChars)) {
      const piece = t.slice(0, maxChars)
      if (!cur) cur = piece
      else if (cur.length + SEP.length + piece.length <= maxChars) cur += SEP + piece
      else {
        parts.push(cur)
        cur = piece
      }
    }
  }
  if (cur) parts.push(cur)
  return parts
}

/** Ước lượng token hạn mức AI để tạo chỉ mục (≈ 2 ký tự/token như backend estimate_tokens). */
const estimateTokens = (chars: number) => Math.ceil(chars / 2)

type Phase = 'idle' | 'reading' | 'analyzing'
interface PendingSave {
  parts: string[]
  label: string
}

/**
 * Trạng thái trang hiện tại cho rail — chỉ đọc metadata tab, không truy cập nội dung khi chưa bấm Quét.
 * URL tab chỉ hiển thị cho extension khi đã có quyền đọc (optional host permissions hoặc activeTab tạm
 * thời); đã cấp quyền mà URL vẫn ẩn → trang hệ thống/trình xem PDF (không quét được).
 */
const PAGE_STATUS = {
  ready: { text: 'Trang có thể quét tự động', hint: 'QuickAssist chỉ đọc trang khi bạn bấm Quét trang.' },
  permission: { text: 'Cần cấp quyền đọc trang', hint: 'Bấm Quét trang — sẽ được hỏi quyền đọc trang trước khi quét.' },
  unsupported: { text: 'Trang này không hỗ trợ quét', hint: 'Trang hệ thống hoặc trình xem PDF không quét được — dùng Dán thủ công.' },
} as const
type PageStatusKey = keyof typeof PAGE_STATUS

export function PageFinderView({ folders, onGoSettings }: { folders: Folder[]; onGoSettings: () => void }) {
  const [query, setQuery] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [result, setResult] = useState<PageMatchRun>()
  const [error, setError] = useState<SerializedError>()
  const [pasteMode, setPasteMode] = useState(false)
  const [pasted, setPasted] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [folderId, setFolderId] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirm, setConfirm] = useState<PendingSave>()
  const [pageStatus, setPageStatus] = useState<PageStatusKey | null>(null)
  const folderSelectId = useId()
  const toast = useToast()

  useBroadcast((e) => {
    if (e.type === 'pageMatch/progress') setPhase((p) => (p === 'reading' ? 'analyzing' : p))
  })

  // Trạng thái trang: đổi khi người dùng chuyển tab hoặc trang điều hướng.
  useEffect(() => {
    if (pasteMode) return
    let alive = true
    const check = async () => {
      try {
        const tabs = chrome.tabs?.query ? await chrome.tabs.query({ active: true, lastFocusedWindow: true }) : []
        const granted = (await chrome.permissions?.contains?.({ origins: ['http://*/*', 'https://*/*'] })) ?? false
        if (!alive) return
        const url = tabs[0]?.url
        setPageStatus(url && /^https?:/.test(url) ? 'ready' : granted ? 'unsupported' : 'permission')
      } catch {
        if (alive) setPageStatus(null)
      }
    }
    void check()
    chrome.tabs?.onActivated?.addListener(check)
    chrome.tabs?.onUpdated?.addListener(check)
    return () => {
      alive = false
      chrome.tabs?.onActivated?.removeListener(check)
      chrome.tabs?.onUpdated?.removeListener(check)
    }
  }, [pasteMode])

  const scan = async (e?: FormEvent) => {
    e?.preventDefault()
    const q = query.trim()
    if (!q || phase !== 'idle' || (pasteMode && !pasted.trim())) return
    setPhase(pasteMode ? 'analyzing' : 'reading')
    setError(undefined)
    setResult(undefined)
    try {
      const r = await rpc('pageMatch/run', pasteMode ? { query: q, text: pasted } : { query: q })
      setResult(r)
      // Đoạn đã được AI xác nhận được tích sẵn; kết quả "theo điểm" để người dùng tự chọn.
      setSelected(new Set(r.items.filter((i) => i.verified).map((i) => i.id)))
    } catch (err) {
      setError(toSerialized(err))
    } finally {
      setPhase('idle')
    }
  }

  const togglePaste = () => {
    if (phase !== 'idle') return
    setPasteMode((v) => !v)
    setError(undefined)
    setResult(undefined)
  }

  const grantAndRetry = async () => {
    // Quyền tuỳ chọn, chỉ xin khi người dùng bấm (H01: không có host permission thường trực).
    const granted = await chrome.permissions
      .request({ origins: ['http://*/*', 'https://*/*'] })
      .catch(() => false)
    if (granted) void scan()
    else toast('Chưa được cấp quyền đọc trang', 'error')
  }

  const items = result?.items ?? []
  const fromPaste = result !== undefined && result.tabId == null
  const chosen = useMemo(() => items.filter((i) => selected.has(i.id)), [items, selected])
  const toggle = (id: string) =>
    setSelected((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })

  const highlight = async (list: PageMatchItem[]) => {
    if (!result || result.tabId == null || list.length === 0) return
    const r = await rpc('pageMatch/highlight', { tabId: result.tabId, items: list.map((i) => ({ text: i.text, occ: i.occ })) }).catch(
      () => ({ ok: false, found: 0, total: list.length }),
    )
    if (!r.ok) toast('Không tìm thấy đoạn trên trang (trang có thể đã thay đổi)', 'error')
  }

  const requestSave = (texts: string[], label: string) => {
    const parts = buildNoteParts(texts)
    const chars = parts.reduce((n, p) => n + p.length, 0)
    if (parts.length > 1 || chars > CONFIRM_CHARS) setConfirm({ parts, label })
    else void save(parts, label)
  }

  const save = async (parts: string[], label: string) => {
    if (!result) return
    setConfirm(undefined)
    setSaving(true)
    const title = query.trim().slice(0, 480) || result.title
    let saved = 0
    try {
      for (const [i, content] of parts.entries()) {
        await rpc('notes/create', {
          content,
          title: parts.length > 1 ? `${title} (${i + 1}/${parts.length})` : title,
          url: result.url ?? null,
          folderId: folderId || null,
        })
        saved += 1
      }
      toast(parts.length > 1 ? `Đã lưu ${label} thành ${parts.length} ghi chú` : `Đã lưu ${label} thành ghi chú`)
    } catch (err) {
      const e = toSerialized(err)
      setError(saved > 0 ? { ...e, message: `Đã lưu ${saved}/${parts.length} phần. ${e.message}` } : e)
    } finally {
      setSaving(false)
    }
  }

  const busy = phase !== 'idle'
  const confirmChars = confirm ? confirm.parts.reduce((n, p) => n + p.length, 0) : 0
  const status = pageStatus ? PAGE_STATUS[pageStatus] : null
  const allSelected = chosen.length === items.length

  // Textarea 2 dòng (theo wireframe): Enter quét luôn, Shift+Enter xuống dòng.
  const submitOnEnter = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void scan()
    }
  }

  return (
    <section className="pagematch" aria-label="Tìm trong trang">
      <aside className="pf-rail" aria-label="Truy vấn">
        <div className="pf-rail-top">
          <h2 className="pf-headline">{pasteMode ? 'Dán nội dung để tìm và gom đoạn' : 'Nêu câu hỏi, nội dung trên trang sẽ trả lời cho bạn'}</h2>
          <p className="pf-lede">
            {pasteMode
              ? 'Dán văn bản từ PDF, Word, chat, email… AI tìm và gom các đoạn khớp để bạn chọn lưu.'
              : 'QuickAssist đọc trang đang mở, gom các đoạn liên quan và để bạn chọn lưu thành một ghi chú.'}
          </p>
        </div>

        <form className="pf-composer" role="search" aria-label="Tìm trong trang" onSubmit={(e) => void scan(e)}>
          {!pasteMode && (
            <p className={`pf-status is-${pageStatus ?? 'unknown'}`} title={status?.hint}>
              <span className="status-dot" aria-hidden />
              <span>{phase === 'reading' ? 'Đang đọc trang…' : (status?.text ?? 'Đang kiểm tra trang…')}</span>
            </p>
          )}
          {pasteMode && (
            <div className="stack">
              <TextArea
                aria-label="Nội dung để quét"
                rows={4}
                value={pasted}
                placeholder="Dán nội dung vào đây (Ctrl+V)…"
                onChange={(e) => setPasted(e.target.value)}
              />
              <small className="muted">{pasted.length.toLocaleString('vi-VN')} ký tự · khoảng 50 000 ký tự đầu được quét</small>
            </div>
          )}
          <TextArea
            className="pf-query"
            rows={2}
            maxLength={500}
            aria-label={pasteMode ? 'Bạn cần tìm gì trong nội dung này?' : 'Bạn cần tìm gì trên trang này?'}
            placeholder="Mô tả nội dung cần gom…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={submitOnEnter}
          />
          <div className="pf-composer-actions">
            <Button type="submit" busy={busy} disabled={!query.trim() || (pasteMode && !pasted.trim())}>
              <Icon name="scan" size={15} />
              {pasteMode ? 'Quét nội dung' : 'Quét trang'}
            </Button>
            <Button type="button" variant="quiet" disabled={busy} onClick={togglePaste}>
              <Icon name="clipboard" size={15} />
              {pasteMode ? 'Huỷ dán' : 'Dán thủ công'}
            </Button>
          </div>
          <p className="pf-reassure">
            <Icon name="lock" size={13} />
            Không tự lưu — bạn chọn đoạn và bấm Lưu.
          </p>
        </form>
      </aside>

      <section className="pf-results">
        {result && !busy && items.length > 0 && (
          <header className="pf-head">
            {result.mode === 'full_page' && (
              <Banner tone="info">
                <div className="pf-notice">
                  <Icon name="info" size={16} />
                  <span>
                    {fromPaste ? 'Hầu như toàn bộ nội dung khớp truy vấn (' : 'Hầu như cả trang khớp truy vấn ('}
                    <strong>{Math.round(result.match_ratio * 100)}%</strong>) — nên lưu toàn bộ thay vì chọn từng đoạn.
                  </span>
                </div>
              </Banner>
            )}
            <div className="pf-titlerow">
              <div>
                <h2 className="pf-title">Kết quả truy vấn</h2>
                <p className="pf-meta" aria-live="polite">
                  <span>
                    Thấy <strong>{items.length}</strong> đoạn
                  </span>
                  <span className="meta-dot" aria-hidden />
                  <span>
                    đã chọn <strong>{chosen.length}</strong>
                  </span>
                </p>
              </div>
              <div className="pf-headactions">
                {!fromPaste && (
                  <Button variant="link" size="sm" onClick={() => void highlight(items)}>
                    <Icon name="locate" size={14} />
                    Xem tất cả trên trang
                  </Button>
                )}
                <Button variant="ghost" size="sm" onClick={() => setSelected(new Set(allSelected ? [] : items.map((i) => i.id)))}>
                  {allSelected ? 'Bỏ chọn' : 'Chọn tất cả'}
                </Button>
              </div>
            </div>
          </header>
        )}

        <div className="pf-scroll">
          {phase === 'reading' && <Spinner label="Đang đọc trang…" />}
          {phase === 'analyzing' && <Spinner label="Đang phân tích & thẩm định bằng AI…" />}

          {error && !busy && (
            <ErrorState
              error={error}
              onRetry={['QUOTA_EXCEEDED', 'PAGE_ACCESS_DENIED', 'PAGE_TOO_LONG', 'PAGE_NO_CONTENT'].includes(error.code) ? undefined : () => void scan()}
              action={
                error.code === 'QUOTA_EXCEEDED' ? (
                  <Button variant="link" size="sm" onClick={onGoSettings}>
                    Xem hạn mức
                  </Button>
                ) : error.code === 'PAGE_ACCESS_DENIED' ? (
                  <Button variant="ghost" size="sm" onClick={() => void grantAndRetry()}>
                    Cho phép đọc trang
                  </Button>
                ) : undefined
              }
            />
          )}

          {result && !busy && (
            <>
              {result.truncated && (
                <Banner tone="info">
                  {fromPaste
                    ? 'Nội dung rất dài — chỉ phần đầu (khoảng 50 000 ký tự) được quét.'
                    : 'Trang rất dài — chỉ phần đầu (khoảng 50 000 ký tự nội dung) được quét.'}
                </Banner>
              )}
              {result.warning === 'VERIFY_UNAVAILABLE' && items.length > 0 && (
                <Banner tone="warn">AI chưa thẩm định được lần này — các đoạn dưới đây xếp theo độ tương đồng. Hãy kiểm tra trước khi lưu.</Banner>
              )}
              {items.length === 0 ? (
                <EmptyState title="Không tìm thấy đoạn nào đủ tin cậy">
                  Thử diễn đạt khác, dùng từ khoá có trong {fromPaste ? 'nội dung' : 'trang'}, hoặc bôi đen thủ công đoạn cần ghi chú.
                </EmptyState>
              ) : (
                <ol className="pf-list" aria-label="Các đoạn tìm thấy">
                  {items.map((it, n) => (
                    <li key={it.id} className={`card pf-card${selected.has(it.id) ? ' is-selected' : ''}`}>
                      <div className="pf-cardhead">
                        <label className="pf-select">
                          <input type="checkbox" checked={selected.has(it.id)} onChange={() => toggle(it.id)} aria-label={`Chọn đoạn ${n + 1}`} />
                          <span className="pf-index">Đoạn {n + 1}</span>
                        </label>
                        <span
                          className={`pf-sim${it.verified ? '' : ' is-unverified'}`}
                          title={it.verified ? 'AI đã xác nhận đoạn này khớp truy vấn' : 'Chưa thẩm định — xếp theo độ tương đồng'}
                        >
                          <span className="sr-only">Độ tương đồng </span>
                          {Math.round(it.score * 100)}%
                        </span>
                        <Button
                          variant="link"
                          size="sm"
                          disabled={fromPaste}
                          title={fromPaste ? 'Nội dung dán không có trang gốc để xem' : undefined}
                          onClick={() => void highlight([it])}
                        >
                          Xem trên trang
                        </Button>
                      </div>
                      <p className="pf-text">{it.text}</p>
                    </li>
                  ))}
                </ol>
              )}
            </>
          )}

          {!result && !error && !busy && (
            <EmptyState title="Gom nội dung theo ý bạn">
              Thay vì bôi đen từng đoạn, hãy mô tả điều bạn cần — QuickAssist đọc trang đang mở, tìm các đoạn liên quan và để bạn chọn lưu thành
              một ghi chú. Không có trang web? Bấm <strong>Dán thủ công</strong> để quét văn bản từ PDF, Word, chat, email…
            </EmptyState>
          )}
        </div>

        {result && !busy && items.length > 0 && (
          <footer className="pf-savebar" aria-label="Lưu kết quả">
            <div className="pf-folder">
              <label htmlFor={folderSelectId}>Lưu vào thư mục</label>
              <div className="pf-select-wrap">
                <Select id={folderSelectId} value={folderId} onChange={(e) => setFolderId(e.target.value)}>
                  <option value="">Inbox</option>
                  {folders.filter((f) => !f.is_default).map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                    </option>
                  ))}
                </Select>
                <Icon name="chevron-down" size={15} />
              </div>
            </div>
            <div className="pf-save-actions">
              <div className="row">
                <Button busy={saving} disabled={chosen.length === 0} onClick={() => requestSave(chosen.map((i) => i.text), `${chosen.length} đoạn`)}>
                  <Icon name="check" size={15} />
                  Lưu lựa chọn
                </Button>
                <span className="pf-count">{chosen.length} đoạn</span>
              </div>
              {result.mode === 'full_page' && (
                <div className="row">
                  <Button
                    variant="ghost"
                    busy={saving}
                    onClick={() =>
                      requestSave(
                        result.full_text ? result.full_text.split(SEP) : items.map((i) => i.text),
                        fromPaste ? 'toàn bộ nội dung' : 'cả trang',
                      )
                    }
                  >
                    <Icon name="layers" size={15} />
                    Lưu toàn bộ
                  </Button>
                  <small className="muted">≈ {result.total_chars.toLocaleString('vi-VN')} ký tự</small>
                </div>
              )}
            </div>
          </footer>
        )}
      </section>

      <ConfirmDialog
        open={!!confirm}
        title="Lưu nội dung lớn?"
        message={
          confirm
            ? `Nội dung dài ${confirmChars.toLocaleString('vi-VN')} ký tự${confirm.parts.length > 1 ? `, vượt giới hạn một ghi chú nên sẽ được lưu thành ${confirm.parts.length} ghi chú` : ''}. Tạo chỉ mục tìm kiếm sẽ dùng khoảng ${estimateTokens(confirmChars).toLocaleString('vi-VN')} token hạn mức AI.`
            : ''
        }
        confirmLabel="Lưu"
        onConfirm={() => confirm && void save(confirm.parts, confirm.label)}
        onCancel={() => setConfirm(undefined)}
      />
    </section>
  )
}
