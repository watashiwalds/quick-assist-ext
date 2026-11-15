/**
 * Card "Nhà cung cấp AI" (ADR-0016 §6.2): người dùng nhập key/base_url/model ngay trong Cài
 * đặt — server proxy mọi lời gọi AI, key chỉ nằm trong DB mã hoá (không storage, không log).
 * Preset chỉ điền giá trị mẫu; mọi ô vẫn sửa được. Lưu khi fingerprint embedding đổi →
 * server tự rebuild chỉ mục → hiện banner tiến độ.
 */
import { useState } from 'react'
import type { AiProvider, AiSettings, AiTestResult } from '@/shared/api/types'
import { rpc } from '@/shared/messaging/client'
import { Banner, Button, ConfirmDialog, ErrorState, Field, Input, Select, Spinner, useToast } from '../../components'
import { useAction, useAsync } from '../../lib/hooks'

/** Mẫu cấu hình — chỉ điền giá trị mặc định, người dùng sửa được mọi ô (D10/D11). */
const PRESETS: Array<{ id: string; label: string; provider: AiProvider; base_url: string; chat_model: string; embedding_model: string }> = [
  { id: 'openai', label: 'OpenAI', provider: 'openai', base_url: 'https://api.openai.com/v1', chat_model: 'gpt-4o-mini', embedding_model: 'text-embedding-3-small' },
  { id: 'gemini', label: 'Google Gemini', provider: 'gemini', base_url: 'https://generativelanguage.googleapis.com/v1beta/models', chat_model: 'gemma-4-31b-it', embedding_model: 'gemini-embedding-001' },
  { id: 'ollama', label: 'Ollama (local)', provider: 'openai', base_url: 'http://localhost:11434/v1', chat_model: 'llama3.1', embedding_model: 'nomic-embed-text' },
  { id: 'lmstudio', label: 'LM Studio', provider: 'openai', base_url: 'http://localhost:1234/v1', chat_model: '', embedding_model: '' },
  { id: 'llamacpp', label: 'llama.cpp', provider: 'openai', base_url: 'http://localhost:8080/v1', chat_model: '', embedding_model: '' },
  { id: 'custom', label: 'Tuỳ chỉnh', provider: 'openai', base_url: '', chat_model: '', embedding_model: '' },
]

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

  const testAct = useAction()
  const saveAct = useAction()
  const resetAct = useAction()

  const data = cfg.data
  const form: FormState = { ...fromSaved(data), ...edits }
  const setField = (patch: Partial<FormState>) => setEdits((prev) => ({ ...prev, ...patch }))
  const byok = data?.mode === 'byok'
  const notes = data?.rebuild_note_count ?? 0

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

  if (cfg.loading && !cfg.data)
    return (
      <div className="card stack" aria-label="Nhà cung cấp AI">
        <strong>Nhà cung cấp AI</strong>
        <Spinner label="Đang tải cấu hình AI…" />
      </div>
    )
  if (cfg.error)
    return (
      <div className="card stack" aria-label="Nhà cung cấp AI">
        <strong>Nhà cung cấp AI</strong>
        <ErrorState error={cfg.error} onRetry={cfg.reload} />
      </div>
    )

  const suggestions = PRESETS.find((p) => p.id === preset)

  return (
    <div className="card stack" aria-label="Nhà cung cấp AI">
      <div className="row spread">
        <strong>Nhà cung cấp AI</strong>
        <small className="muted">
          {byok
            ? <>AI của bạn: {data?.provider} · {data?.embedding_model}</>
            : <>Đang dùng cấu hình server: {data?.server_default.provider} · {data?.server_default.embedding_model}</>}
        </small>
      </div>

      {rebuild && (
        <Banner tone="info">
          Đang dựng lại chỉ mục ngữ nghĩa của {rebuild.notes} ghi chú. Tìm kiếm từ khoá vẫn hoạt động
          trong lúc dựng; xong sẽ tự dùng model mới.{' '}
          <Button variant="link" size="sm" onClick={() => setRebuild(null)}>Ẩn</Button>
        </Banner>
      )}

      <Field label="Mẫu cấu hình" hint="Chỉ điền giá trị gợi ý — mọi ô bên dưới vẫn sửa được.">
        {(id) => (
          <Select
            id={id}
            value={preset}
            onChange={(e) => {
              const p = PRESETS.find((x) => x.id === e.target.value)
              setPreset(e.target.value)
              if (p) setField({ provider: p.provider, base_url: p.base_url, chat_model: p.chat_model, embedding_model: p.embedding_model })
            }}
          >
            <option value="">— Chọn mẫu —</option>
            {PRESETS.map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </Select>
        )}
      </Field>

      <Field label="Base URL" hint="Endpoint tương thích OpenAI hoặc Gemini API.">
        {(id) => (
          <Input
            id={id}
            type="url"
            placeholder="https://api.openai.com/v1"
            value={form.base_url}
            maxLength={512}
            onChange={(e) => setField({ base_url: e.target.value })}
          />
        )}
      </Field>

      <Field
        label="API key"
        hint={
          clearKey ? 'Sẽ XOÁ key đã lưu khi bấm Lưu (model local không cần key).'
          : data?.has_key ? `Đã lưu ${data.key_hint ?? ''} — gõ key mới để thay, bỏ trống để giữ.`
          : 'Không bắt buộc với model tự host (Ollama, llama.cpp…).'
        }
      >
        {(id) => (
          <div className="row">
            <Input
              id={id}
              type={showKey ? 'text' : 'password'}
              autoComplete="off"
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

      <Field label="Model chat">
        {(id) => (
          <>
            <Input
              id={id}
              list={`qa-chat-models-${id}`}
              value={form.chat_model}
              maxLength={100}
              placeholder={data?.server_default.chat_model ?? 'gpt-4o-mini'}
              onChange={(e) => setField({ chat_model: e.target.value })}
            />
            <datalist id={`qa-chat-models-${id}`}>
              {suggestions?.chat_model && <option value={suggestions.chat_model} />}
            </datalist>
          </>
        )}
      </Field>

      <Field label="Model embedding" hint="Đổi model embedding sẽ dựng lại chỉ mục tìm kiếm.">
        {(id) => (
          <>
            <Input
              id={id}
              list={`qa-embed-models-${id}`}
              value={form.embedding_model}
              maxLength={100}
              placeholder={data?.server_default.embedding_model ?? 'text-embedding-3-small'}
              onChange={(e) => setField({ embedding_model: e.target.value })}
            />
            <datalist id={`qa-embed-models-${id}`}>
              {suggestions?.embedding_model && <option value={suggestions.embedding_model} />}
            </datalist>
          </>
        )}
      </Field>

      <details>
        <summary className="muted">Nâng cao</summary>
        <Field label="Timeout (giây)" hint="Bỏ trống = dùng giá trị của server (90s). Trong khoảng 5–600.">
          {(id) => (
            <Input
              id={id}
              type="number"
              min={5}
              max={600}
              step={1}
              placeholder="90"
              value={form.timeout_seconds}
              onChange={(e) => setField({ timeout_seconds: e.target.value })}
            />
          )}
        </Field>
      </details>

      {testAct.error && <ErrorState error={testAct.error} />}
      {saveAct.error && <ErrorState error={saveAct.error} />}
      {resetAct.error && <ErrorState error={resetAct.error} />}

      {tooLarge ? (
        <Banner tone="error">
          Model trả {nativeDim} chiều &gt; 1536 — không thể lưu. Chọn model khác hoặc sửa endpoint.
        </Banner>
      ) : test && test.ok ? (
        <Banner tone="ok">
          Kết nối tốt: embedding {test.embedding?.model} · {test.embedding?.dim} chiều
          {test.embedding?.padded ? ' (sẽ pad về 1536)' : ''} · {test.embedding?.latency_ms}ms — chat{' '}
          {test.chat?.model} · {test.chat?.latency_ms}ms{test.chat?.sample ? `: “${test.chat.sample}”` : ''}
        </Banner>
      ) : test ? (
        <Banner tone="error">
          Lỗi ở {test.stage === 'chat' ? 'bước chat' : 'bước embedding'}: {test.message}
        </Banner>
      ) : null}

      {warnUntested && !tested && !tooLarge && (
        <Banner tone="warn">
          Cấu hình chưa được kiểm tra (hoặc đã đổi sau lần test) — bấm “Kiểm tra kết nối” để xác nhận
          trước khi Lưu. Bạn vẫn có thể lưu, nhưng nếu endpoint/model sai, index sẽ lỗi.
        </Banner>
      )}

      <div className="row">
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
        {byok && (
          <Button variant="ghost" busy={resetAct.busy} onClick={() => (notes > 0 ? setConfirming('reset') : doReset())}>
            Dùng cấu hình server
          </Button>
        )}
      </div>
      {!byok && (
        <small className="muted">
          Bạn đang dùng AI của server. Điền cấu hình trên rồi bấm Lưu để dùng AI của riêng bạn (BYOK).
        </small>
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
