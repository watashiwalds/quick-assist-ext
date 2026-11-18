/**
 * Mục "Dịch vụ AI" (ADR-0016 §6.2): chọn dùng AI của server hay endpoint riêng; người dùng nhập
 * key/base_url/model ngay trong Cài đặt — server proxy mọi lời gọi AI, key chỉ nằm trong DB mã hoá
 * (không storage, không log). Preset chỉ điền giá trị mẫu; mọi ô vẫn sửa được. Lưu khi fingerprint
 * embedding đổi → server tự rebuild chỉ mục → hiện banner tiến độ.
 */
import { useId, useState } from 'react'
import type { AiProvider, AiSettings, AiTestResult } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Banner, Button, ConfirmDialog, ErrorState, Field, Icon, Input, Spinner, useToast } from '../../components'
import { useAction, useAsync } from '../../lib/hooks'

/** Mẫu cấu hình — chỉ điền giá trị mặc định, người dùng sửa được mọi ô (D10/D11). */
const PRESETS: Array<{
  id: string
  label: string
  /** Nhãn ngắn để vừa hàng preset ở side panel. */
  short?: string
  provider: AiProvider
  base_url: string
  chat_model: string
  embedding_model: string
}> = [
  { id: 'openai', label: 'OpenAI', provider: 'openai', base_url: 'https://api.openai.com/v1', chat_model: 'gpt-4o-mini', embedding_model: 'text-embedding-3-small' },
  { id: 'gemini', label: 'Google Gemini', short: 'Gemini', provider: 'gemini', base_url: 'https://generativelanguage.googleapis.com/v1beta/models', chat_model: 'gemma-4-31b-it', embedding_model: 'gemini-embedding-001' },
  { id: 'ollama', label: 'Ollama (local)', short: 'Ollama', provider: 'openai', base_url: 'http://localhost:11434/v1', chat_model: 'llama3.1', embedding_model: 'nomic-embed-text' },
  { id: 'lmstudio', label: 'LM Studio', provider: 'openai', base_url: 'http://localhost:1234/v1', chat_model: '', embedding_model: '' },
  { id: 'llamacpp', label: 'llama.cpp', provider: 'openai', base_url: 'http://localhost:8080/v1', chat_model: '', embedding_model: '' },
  { id: 'custom', label: 'Tuỳ chỉnh', provider: 'openai', base_url: '', chat_model: '', embedding_model: '' },
]

const PROVIDER_LABEL: Record<string, string> = { openai: 'OpenAI', gemini: 'Google Gemini' }

interface FormState {
  provider: AiProvider
  base_url: string
  chat_model: string
  embedding_model: string
  timeout_seconds: string
  /** Chỉ nằm trong ô input của form; KHÔNG bao giờ được lưu vào chrome.storage (nghiệm thu #3). */
  api_key_input: string
}

const EMPTY: FormState = {
  provider: 'openai', base_url: '', chat_model: '', embedding_model: '', timeout_seconds: '', api_key_input: '',
}

/** Fingerprint embedding = provider|base_url|model → các ô này đổi là có thể phải rebuild. */
function embedFieldsChanged(saved: AiSettings | undefined, f: FormState): boolean {
  if (!saved) return false
  return saved.provider !== f.provider || saved.base_url !== f.base_url || saved.embedding_model !== f.embedding_model
}

/** Giá trị form suy ra từ cấu hình đã lưu (mode inherit → các ô trống, placeholder gợi ý). */
function fromSaved(s: AiSettings | undefined): FormState {
  if (!s) return EMPTY
  return {
    provider: s.provider ?? 'openai',
    base_url: s.base_url ?? '',
    chat_model: s.chat_model ?? '',
    embedding_model: s.embedding_model ?? '',
    timeout_seconds: s.timeout_seconds != null ? String(s.timeout_seconds) : '',
    api_key_input: '',
  }
}

export function ProviderCard({ onChanged }: { onChanged?: () => void }) {
  const cfg = useAsync(() => rpc('ai/config/get'), [])
  const toast = useToast()
  const modeName = useId()
  // Derived state: form = giá trị đã lưu + bản ghi local (chỉ các ô người dùng đã chỉnh).
  // Không dùng useEffect sync → không race, không clobber khi đang gõ.
  const [edits, setEdits] = useState<Partial<FormState>>({})
  const [preset, setPreset] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [clearKey, setClearKey] = useState(false) // "Xoá key" → gửi api_key="" khi Lưu
  const [confirming, setConfirming] = useState<null | 'save' | 'reset'>(null)
  const [rebuild, setRebuild] = useState<{ notes: number } | null>(null) // banner tiến độ
  const [test, setTest] = useState<AiTestResult | null>(null)
  const [testedFor, setTestedFor] = useState<string | null>(null) // signature của lần test
  const [warnUntested, setWarnUntested] = useState(false) // bấm Lưu khi chưa test
  // Người dùng có thể xem trước form endpoint trước khi lưu (mode server → endpoint riêng).
  const [modeDraft, setModeDraft] = useState<'server' | 'endpoint' | null>(null)

  const testAct = useAction()
  const saveAct = useAction()
  const resetAct = useAction()

  const data = cfg.data
  const form: FormState = { ...fromSaved(data), ...edits }
  const setField = (patch: Partial<FormState>) => {
    setEdits((prev) => ({ ...prev, ...patch }))
    setPreset('custom') // sửa tay → chuyển preset sang “Tuỳ chỉnh”
  }
  const mode = modeDraft ?? (data?.mode === 'byok' ? 'endpoint' : 'server')
  const notes = data?.rebuild_note_count ?? 0

  // Có thay đổi chưa lưu → banner nhắc bấm Lưu (rời màn/đóng side panel sẽ mất).
  const dirty =
    Object.keys(edits).length > 0 ||
    clearKey ||
    (modeDraft === 'endpoint' && data?.mode !== 'byok')

  // Test chỉ còn "hiệu lực" khi các trường ảnh hưởng số chiều chưa đổi sau lần test.
  const signature = () => JSON.stringify([form.provider, form.base_url.trim(), form.embedding_model.trim()])
  const tested = test != null && testedFor === signature()
  const nativeDim = tested ? (test.embedding_dim ?? test.embedding?.dim) : undefined
  const tooLarge = nativeDim != null && nativeDim > 1536

  /** Input cho PUT/POST: key gõ mới → gửi; bỏ trống mà đã lưu → null (giữ key cũ); "Xoá key" → "". */
  const buildInput = () => {
    const key = form.api_key_input.trim()
    return {
      mode: 'byok' as const,
      provider: form.provider,
      base_url: form.base_url.trim(),
      chat_model: form.chat_model.trim(),
      embedding_model: form.embedding_model.trim(),
      // Advisory: chỉ gửi khi biết chắc từ lần test khớp form hiện tại (tránh gửi dim cũ).
      embedding_dim: tested && nativeDim && nativeDim > 0 ? nativeDim : undefined,
      timeout_seconds: form.timeout_seconds ? Number(form.timeout_seconds) : null,
      api_key: clearKey ? '' : key ? key : data?.has_key ? null : undefined,
    }
  }
  const testInput = () => {
    // AISTestIn không nhận embedding_dim (extra="forbid" → 422 nếu gửi thừa).
    const { mode: _mode, embedding_dim: _dim, ...rest } = buildInput()
    return rest
  }

  const afterSave = (res: AiSettings) => {
    cfg.setData(res) // form suy ra lại từ cấu hình mới; xoá bản ghi local
    setEdits({})
    setClearKey(false)
    setTest(null)
    setTestedFor(null)
    setWarnUntested(false)
    setModeDraft(null)
    setRebuild(res.rebuild?.required ? { notes: res.rebuild.notes } : null)
    toast(res.rebuild?.required ? 'Đã lưu — đang dựng lại chỉ mục ngữ nghĩa' : 'Đã lưu cấu hình AI')
    onChanged?.()
  }

  const doSave = () => void saveAct.run(() => rpc('ai/config/set', buildInput()).then(afterSave))
  const doReset = () => void resetAct.run(() => rpc('ai/config/reset').then(afterSave))
  const onSave = () => {
    if (tooLarge) {
      toast(`Model embedding trả ${nativeDim} chiều > 1536 — không thể lưu.`, 'error')
      return
    }
    if (!tested) setWarnUntested(true) // cảnh báo nhưng vẫn cho lưu (server là guard cuối)
    // Rebuild xảy ra khi hàm embedding đổi (provider/base_url/model) hoặc lần đầu chuyển từ
    // cấu hình server sang BYOK — server mới là nơi chốt; dialog chỉ để xác nhận trước.
    const mayRebuild = embedFieldsChanged(data, form) || data?.mode !== 'byok'
    if (mayRebuild && notes > 0) setConfirming('save')
    else doSave()
  }

  const chooseServer = () => {
    if (data?.mode !== 'byok') {
      setModeDraft('server')
      return
    }
    // Đang BYOK → cần gọi ai/config/reset; có ghi chú thì xác nhận trước.
    if (notes > 0) setConfirming('reset')
    else doReset()
  }

  const applyPreset = (p: (typeof PRESETS)[number]) => {
    setPreset(p.id)
    // “Tuỳ chỉnh” chỉ đánh dấu chế độ nhập tay, không xoá giá trị đang có.
    if (p.id === 'custom') return
    setEdits((prev) => ({
      ...prev,
      provider: p.provider,
      base_url: p.base_url,
      chat_model: p.chat_model,
      embedding_model: p.embedding_model,
    }))
  }

  if (cfg.loading && !cfg.data)
    return (
      <div className="settings-ai" aria-label="Dịch vụ AI">
        <Spinner label="Đang tải cấu hình AI…" />
      </div>
    )
  if (cfg.error)
    return (
      <div className="settings-ai" aria-label="Dịch vụ AI">
        <ErrorState error={cfg.error} onRetry={cfg.reload} />
      </div>
    )

  const suggestions = PRESETS.find((p) => p.id === preset)
  const server = data?.server_default

  return (
    <div className="settings-ai" aria-label="Dịch vụ AI">
      {rebuild && (
        <Banner tone="info">
          <span className="banner-row">
            <Icon name="sync" size={15} />
            <span>
              Đang dựng lại chỉ mục ngữ nghĩa của {rebuild.notes} ghi chú. Tìm kiếm từ khoá vẫn hoạt động
              trong lúc dựng; xong sẽ tự dùng model mới.{' '}
              <Button variant="link" size="sm" onClick={() => setRebuild(null)}>Ẩn</Button>
            </span>
          </span>
        </Banner>
      )}

      <fieldset className="settings-mode">
        <legend>Nguồn AI</legend>
        <div className="settings-segmented">
          <label className="settings-segment">
            <input type="radio" name={modeName} checked={mode === 'server'} onChange={chooseServer} />
            <span>Dùng AI của server</span>
          </label>
          <label className="settings-segment">
            <input type="radio" name={modeName} checked={mode === 'endpoint'} onChange={() => setModeDraft('endpoint')} />
            <span>Endpoint riêng</span>
          </label>
        </div>
        <p className="settings-hint">
          Chuyển sang “Dùng AI của server” sẽ xoá cấu hình riêng sau khi bạn xác nhận. Chuyển sang endpoint
          riêng để dùng khoá API của bạn.
        </p>
      </fieldset>

      {mode === 'server' && (
        <div className="settings-server">
          <div className="settings-server-head">
            <div>
              <strong>Cấu hình server</strong>
              <p>QuickAssist dùng các giá trị do quản trị viên thiết lập.</p>
            </div>
            <span className="badge badge-ok">Đang áp dụng</span>
          </div>

          <dl className="settings-server-grid">
            <div>
              <dt>Nhà cung cấp</dt>
              <dd>{PROVIDER_LABEL[server?.provider ?? ''] ?? server?.provider}</dd>
            </div>
            <div>
              <dt>Model trò chuyện</dt>
              <dd>{server?.chat_model}</dd>
            </div>
            <div>
              <dt>Model embedding</dt>
              <dd>{server?.embedding_model}</dd>
            </div>
            <div>
              <dt>Thời gian chờ</dt>
              <dd>{data?.timeout_seconds ?? 90} giây</dd>
            </div>
          </dl>

          <p className="settings-server-note">
            <Icon name="info" size={13} />
            <span>
              Bạn không cần khoá API. Chuyển sang endpoint riêng nếu muốn dùng nhà cung cấp hoặc model khác.
            </span>
          </p>
        </div>
      )}

      {mode === 'endpoint' && (
        <form className="settings-form" aria-label="Cấu hình endpoint" onSubmit={(e) => e.preventDefault()}>
          <fieldset className="settings-presets">
            <legend>Preset</legend>
            <div className="settings-preset-list" role="group" aria-label="Preset cấu hình">
              {PRESETS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="settings-preset"
                  aria-pressed={preset === p.id}
                  aria-label={p.label}
                  onClick={() => applyPreset(p)}
                >
                  {p.short ?? p.label}
                </button>
              ))}
            </div>
            <p className="settings-hint">
              Chọn preset để điền giá trị gợi ý; mọi ô bên dưới vẫn sửa được. Sửa tay sẽ chuyển preset sang
              “Tuỳ chỉnh”.
            </p>
          </fieldset>

          <div className="settings-divider" role="presentation" />

          <Field label="URL" hint="Endpoint tương thích OpenAI hoặc Gemini API. Ví dụ: http://localhost:8080/v1.">
            {(id) => (
              <Input
                id={id}
                type="url"
                placeholder="https://api.openai.com/v1"
                value={form.base_url}
                maxLength={512}
                spellCheck={false}
                autoComplete="off"
                onChange={(e) => setField({ base_url: e.target.value })}
              />
            )}
          </Field>

          <Field
            label="Khoá API"
            help="Khoá được mã hoá trên server, không lưu trong trình duyệt."
            hint={
              clearKey ? 'Sẽ XOÁ key đã lưu khi bấm Lưu (model local không cần key).'
              : data?.has_key ? `Đã lưu ${data.key_hint ?? ''} — gõ key mới để thay, bỏ trống để giữ.`
              : 'Không bắt buộc với model tự host (Ollama, llama.cpp…).'
            }
          >
            {(id) => (
              <div className="settings-input-row">
                <Input
                  id={id}
                  type={showKey ? 'text' : 'password'}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder={data?.has_key ? '••••••••' : 'sk-… (tuỳ chọn)'}
                  value={clearKey ? '' : form.api_key_input}
                  maxLength={4096}
                  onChange={(e) => setField({ api_key_input: e.target.value })}
                />
                <Button variant="soft" size="sm" onClick={() => setShowKey(!showKey)}>{showKey ? 'Ẩn' : 'Hiện'}</Button>
                {data?.has_key && !clearKey && (
                  <Button variant="soft" size="sm" onClick={() => setClearKey(true)}>Xoá key</Button>
                )}
                {clearKey && <Button variant="link" size="sm" onClick={() => setClearKey(false)}>Giữ key cũ</Button>}
              </div>
            )}
          </Field>

          <Field
            label="Mô hình trò chuyện"
            help={<>Phục vụ các chức năng: <strong>Hỏi AI</strong>, một số chức năng cần suy luận.</>}
            hint="Gợi ý model lấy từ preset đang chọn."
          >
            {(id) => (
              <>
                <Input
                  id={id}
                  list={`qa-chat-models-${id}`}
                  value={form.chat_model}
                  maxLength={100}
                  spellCheck={false}
                  autoComplete="off"
                  placeholder={server?.chat_model ?? 'gpt-4o-mini'}
                  onChange={(e) => setField({ chat_model: e.target.value })}
                />
                <datalist id={`qa-chat-models-${id}`}>
                  {suggestions?.chat_model && <option value={suggestions.chat_model} />}
                </datalist>
              </>
            )}
          </Field>

          <Field
            label="Mô hình embedding"
            help={<>Phục vụ các chức năng: <strong>Tìm kiếm ngữ nghĩa</strong>, cung cấp bằng chứng.</>}
            hint="Đổi model embedding sẽ dựng lại chỉ mục tìm kiếm."
          >
            {(id) => (
              <>
                <Input
                  id={id}
                  list={`qa-embed-models-${id}`}
                  value={form.embedding_model}
                  maxLength={100}
                  spellCheck={false}
                  autoComplete="off"
                  placeholder={server?.embedding_model ?? 'text-embedding-3-small'}
                  onChange={(e) => setField({ embedding_model: e.target.value })}
                />
                <datalist id={`qa-embed-models-${id}`}>
                  {suggestions?.embedding_model && <option value={suggestions.embedding_model} />}
                </datalist>
              </>
            )}
          </Field>

          <div className="settings-form-actions">
            <Button
              variant="soft"
              busy={testAct.busy}
              onClick={() =>
                void testAct.run(() =>
                  rpc('ai/config/test', testInput()).then((r) => {
                    setTest(r)
                    setTestedFor(signature())
                  }))}
            >
              Kiểm tra kết nối
            </Button>
            <Button busy={saveAct.busy} disabled={tooLarge} onClick={onSave}>Lưu</Button>
            <span className="settings-save-note">Thay đổi chỉ có hiệu lực sau khi bấm Lưu.</span>
          </div>

          {testAct.error && <ErrorState error={testAct.error} />}
          {saveAct.error && <ErrorState error={saveAct.error} />}
          {resetAct.error && <ErrorState error={resetAct.error} />}

          {tooLarge ? (
            <Banner tone="error">
              <span className="banner-row">
                <Icon name="alert" size={15} />
                <span>Model trả {nativeDim} chiều &gt; 1536 — không thể lưu. Chọn model khác hoặc sửa endpoint.</span>
              </span>
            </Banner>
          ) : tested && test && test.ok ? (
            <Banner tone="ok">
              <span className="banner-row">
                <Icon name="check" size={15} />
                <span>
                  Kết nối tốt: embedding {test.embedding?.model} · {test.embedding?.dim} chiều
                  {test.embedding?.padded ? ' (sẽ pad về 1536)' : ''} · {test.embedding?.latency_ms}ms — chat{' '}
                  {test.chat?.model} · {test.chat?.latency_ms}ms{test.chat?.sample ? `: “${test.chat.sample}”` : ''}
                </span>
              </span>
            </Banner>
          ) : tested && test ? (
            <Banner tone="error">
              <span className="banner-row">
                <Icon name="alert" size={15} />
                <span>Lỗi ở {test.stage === 'chat' ? 'bước chat' : 'bước embedding'}: {test.message}</span>
              </span>
            </Banner>
          ) : null}

          {warnUntested && !tested && !tooLarge && (
            <Banner tone="warn">
              <span className="banner-row">
                <Icon name="alert" size={15} />
                <span>
                  <strong>Cấu hình chưa được kiểm tra.</strong> Các trường đã đổi sau lần kiểm tra gần nhất.
                  Bấm “Kiểm tra kết nối” trước khi Lưu để chắc endpoint và model hoạt động; bạn vẫn có thể lưu,
                  nhưng nếu sai, chỉ mục sẽ lỗi.
                </span>
              </span>
            </Banner>
          )}

          {dirty && !tested && !tooLarge && !warnUntested && (
            <Banner tone="warn">
              <span className="banner-row">
                <Icon name="alert" size={15} />
                <span>
                  <strong>Có thay đổi chưa lưu.</strong> Bấm Lưu để áp dụng. Rời màn này hoặc đóng side panel sẽ
                  mất các thay đổi đang nhập.
                </span>
              </span>
            </Banner>
          )}

          <div className="settings-divider" role="presentation" />

          <details className="settings-advanced">
            <summary>
              <span className="settings-advanced-title">Nâng cao</span>
              <span className="settings-advanced-sub">Không thay đổi nếu bạn không hiểu rõ về các giá trị.</span>
              <Icon name="chevron-right" size={15} className="settings-advanced-chevron" />
            </summary>
            <div className="settings-advanced-body">
              <Field
                label="Thời gian chờ phản hồi (Time-out)"
                hint="Bỏ trống để dùng 90 giây của server. Trong khoảng 5–600 giây."
              >
                {(id) => (
                  <div className="settings-input-suffix">
                    <Input
                      id={id}
                      type="number"
                      min={5}
                      max={600}
                      step={1}
                      inputMode="numeric"
                      placeholder="90"
                      value={form.timeout_seconds}
                      onChange={(e) => setField({ timeout_seconds: e.target.value })}
                    />
                    <span aria-hidden="true">giây</span>
                  </div>
                )}
              </Field>
            </div>
          </details>
        </form>
      )}

      <ConfirmDialog
        open={confirming === 'save'}
        title="Dựng lại chỉ mục tìm kiếm?"
        message={`Sẽ dựng lại chỉ mục ngữ nghĩa của ${notes} ghi chú bằng model embedding mới. Tìm kiếm từ khoá vẫn hoạt động trong lúc dựng.`}
        confirmLabel="Lưu và dựng lại"
        busy={saveAct.busy}
        onCancel={() => setConfirming(null)}
        onConfirm={() => {
          setConfirming(null)
          doSave()
        }}
      />
      <ConfirmDialog
        open={confirming === 'reset'}
        title="Dùng lại cấu hình server?"
        message={`Sẽ dựng lại chỉ mục ngữ nghĩa của ${notes} ghi chú theo model của server. Tìm kiếm từ khoá vẫn hoạt động trong lúc dựng.`}
        confirmLabel="Chuyển và dựng lại"
        busy={resetAct.busy}
        onCancel={() => setConfirming(null)}
        onConfirm={() => {
          setConfirming(null)
          doReset()
        }}
      />
    </div>
  )
}
