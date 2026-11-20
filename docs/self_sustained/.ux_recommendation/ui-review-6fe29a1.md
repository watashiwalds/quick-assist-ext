# Kế hoạch sửa UI — từ commit `6fe29a1` đến `HEAD`

> Ngày rà: 18/11/2026 · Base: `6fe29a1e1c00e935618ef83c3f9895bafe72f768` → `76f211a`
> Phạm vi: **frontend extension** (`apps/extension/src/ui/**`, `apps/extension/src/ui/styles.css`, test UI liên quan).
> Không bao gồm backend, schema, hay hành vi RAG/tìm kiếm.
> Tài liệu này **chỉ là kế hoạch** — chưa có thay đổi code nào được áp dụng.

## 0. Quyết định đã chốt

| Vấn đề | Quyết định |
|---|---|
| Header kết quả "Tìm trong trang" ở panel hẹp | **Thu gọn ở `≤720px`**: nhãn sort ngắn (`Theo trang`/`Tin cậy`), đưa link "Xem tất cả trên trang" xuống hàng hint dưới tiêu đề. |
| Phạm vi kế hoạch | **Bao gồm cả refactor**: API `PaneHeader` (bỏ 8 prop className) và dùng lại `ProgressBar` chuẩn cho thanh tiến độ quét. |

## 1. Cách rà & bằng chứng

1. Đọc diff UI trong khoảng commit: `styles.css`, `NotesView`, `PageFinderView`, `SearchView`, `SearchResults`, `NoteCard`, `MoveNotesDialog`, `Sources`, `PaneHeader`, `GroupSection`, `ConfidenceBadge`, `ChatView` (phần Nguồn/composer).
2. Chạy baseline test UI: `npx vitest run tests/ui tests/chat-sources.test.ts tests/group-notes.test.ts tests/search-summary.test.ts` → **11 file / 113 test pass** (chưa sửa gì).
3. Dựng preview ngoài repo (`/tmp/opencode/ui-verify/`) dùng **nguyên `styles.css`** với DOM của `GroupSection`, `PaneHeader`, `.pf-sort`, `composer`, rồi đo bằng chrome-devtools ở 400/440/880/980/1024/1200px và chụp ảnh light/dark.
4. Chạy `axe-core` trên preview: không phát sinh vi phạm do markup mới (các lỗi `landmark-one-main`, `select-name` là do preview tối giản, không thuộc extension).
5. Đối chiếu với ngôn ngữ thị giác hiện có: token A05, `--radius-*`, `--space`, `--pane-pad`, `--card-pad`, nhãn uppercase muted, badge pill, pane header, focus-visible, reduced-motion.

### Số đo đáng chú ý (panel kết quả rộng 400px)

| Phần tử | Hiện tại | Ghi chú |
|---|---|---|
| `.pf-head` (header kết quả) | **cao ~220px** | banner + title row + hint |
| `.pf-titlerow` | **cao 128px** | actions bị đẩy xuống dưới tiêu đề |
| `.pf-headactions` | **cao 61px** (2 hàng) | sort 229px + link + "Chọn tất cả" |
| `.pf-sort` | **229 × 29px** | chiếm gần 2/3 bề ngang |
| Nút sort | **cao 22,7px** | dưới ngưỡng 24px của WCAG 2.2 AA (2.5.8) |
| `.source-group-summary` | badge nằm **dòng riêng** | text tụt xuống dòng dưới |
| Nhãn nhóm vs summary | lệch **2px** (55 vs 53) | `margin-left: 26px` thay vì 28px |

## 2. Danh sách phát hiện

Mức độ theo quy ước review: **Critical** (chặn merge) · **Required** (phải sửa) · **Optional** (nên sửa) · **Nit** (tuỳ).

| ID | Mức | Phát hiện | Bằng chứng |
|---|---|---|---|
| R1 | Required | Badge "Tóm tắt từ ghi chú" bị đẩy sang dòng riêng, summary tụt xuống dưới vì `.source-group-summary` dùng `flex-wrap` với text là anonymous flex item | Ảnh chụp 400px; `.source-group-summary` tại `styles.css:565` |
| R2 | Required | Header kết quả "Tìm trong trang" quá cao ở panel hẹp; sort + link + nút xuống 2 hàng | Đo 220px/128px/61px; `.pf-titlerow` `styles.css:686` |
| R3 | Required | `className="pf-rail-top"` không tồn tại trong CSS → class chết | `PageFinderView.tsx:342`; grep `styles.css` không có |
| R4 | Required | Nút sort cao 22,7px < 24px (WCAG 2.2 AA, 2.5.8) | `.pf-sort button { padding: 3px 9px }` `styles.css:693` |
| R5 | Required | `aria-live="polite"` bao cả `.note-groups` (chứa header/nút) → trình đọc màn hình có thể đọc cả cụm khi mở/đóng nhóm hoặc đổi lựa chọn; số lượng đã được PaneHeader đọc | `NotesView.tsx:318` |
| R6 | Required | Nút "Chọn cả nhóm" dùng `.btn-ghost` có viền → nổi hơn cả header nhóm; khác cách `.pane-actions` xử lý ghost (viền trong suốt) | Ảnh chụp; `.pane-actions .btn-ghost` `styles.css:521` |
| R7 | Optional | Nút "Xem thêm N ghi chú" có `aria-expanded` nhưng thiếu `aria-controls` vì `GroupSection` tự sinh id và không expose | `SearchResults.tsx:60`, `GroupSection.tsx:28` |
| R8 | Optional | `aria-label` đặt trên `div` generic (không phải landmark); các màn khác dùng `<section aria-label>` | `SearchResults.tsx:37`, `NotesView.tsx:266` |
| R9 | Optional | `.pf-card.is-selected` là chỗ duy nhất dùng `color-mix()` tự pha màu, chưa thành token; note-item đang dùng `--accent-soft` | `styles.css:712` |
| R10 | Nit | Summary lệch 2px so với nhãn nhóm | xem §1 |
| R11 | Nit | `ScanScopeDialog` dùng inline `style={{ margin: 0 }}`; dialog chọn phạm vi quét không autofocus nút chính | `PageFinderView.tsx:92-100` |
| R12 | Refactor | `PaneHeader` nhận **8 prop className** — cấu hình thay vì cấu trúc; CSS pane-head vẫn bị nhân đôi giữa `.pane-*` và `.pf-*` | `PaneHeader.tsx:10-58`, `styles.css:515-521` vs `686-690` |
| R13 | Refactor | `.pf-progress-track` là bản gần trùng của `ProgressBar` chuẩn (khác chiều cao/màu/viền, tự làm indeterminate) | `styles.css:701-707`, `State.tsx:65-73` |
| R14 | Nit | Hai `.composer-hint` cạnh nhau (đã đo: **không tràn** ở các bề rộng thực tế nhờ media query ≤720); chỉ là mật độ chữ | `ChatView.tsx:644-645` |
| R15 | Nit | Vùng nhóm "Thư viện" dùng nhãn uppercase 12px, rail dùng 11px; badge nhóm dài "Tóm tắt từ ghi chú" tạo khoảng trống ở panel hẹp | ảnh chụp |

**Đã kiểm tra và đạt (không cần sửa):** màu mới đều qua token; `prefers-reduced-motion` cho skeleton/progress/source chevron; focus-visible cho sort, group toggle, Modal; `aria-expanded`/`aria-controls` của `GroupSection`; `aria-pressed` của sort; đếm kết quả theo `note_count`; `SearchResults` dùng chung Thư viện ↔ Tìm kiếm; badge tin cậy có nhãn `.sr-only`; `title` + `line-clamp` của note card.

## 3. Chi tiết sửa theo từng hạng mục

### R1 — Summary nhóm: badge phải nằm cùng dòng với text

`GroupSection` giữ nguyên markup (badge là `span` inline, text là text node). Chỉ đổi layout summary từ flex sang block:

```css
/* styles.css — thay dòng 565 */
.source-group-summary {
  display: block;
  margin: 0 4px 4px 28px;      /* 28 = 2 head-pad + 6 toggle-pad + 14 icon + 6 gap */
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--muted);
  text-wrap: pretty;
}
.source-group-summary .note-item-badge { margin-right: 6px; }
```

Kết quả mong đợi: "Tóm tắt từ ghi chú" đứng đầu câu, text chảy tiếp và xuống dòng bên dưới badge (giống cách `NoteCard` đang hiển thị badge "Tóm tắt" trong excerpt).

### R2 — Thu gọn header "Tìm trong trang" ở `≤720px`

**(a) Nhãn sort ngắn, giữ nguyên tên truy cập và test hiện tại.** Hai span, button có `aria-label` đầy đủ; span đều `aria-hidden` để tên truy cập không bị nối chuỗi:

```tsx
// PageFinderView.tsx — thay nội dung 2 nút trong .pf-sort
<button
  type="button"
  aria-label="Thứ tự trong trang"
  aria-pressed={sort === 'page'}
  className={sort === 'page' ? 'is-active' : ''}
  onClick={() => setSort('page')}
>
  <span className="pf-sort-long" aria-hidden="true">Thứ tự trong trang</span>
  <span className="pf-sort-short" aria-hidden="true">Theo trang</span>
</button>
<button
  type="button"
  aria-label="Tin cậy giảm dần"
  aria-pressed={sort === 'confidence'}
  className={sort === 'confidence' ? 'is-active' : ''}
  onClick={() => setSort('confidence')}
>
  <span className="pf-sort-long" aria-hidden="true">Tin cậy giảm dần</span>
  <span className="pf-sort-short" aria-hidden="true">Tin cậy</span>
</button>
```

```css
.pf-sort-short { display: none; }
@media (max-width: 720px) {
  .pf-sort-long { display: none; }
  .pf-sort-short { display: inline; }
}
```

**(b) Đưa "Xem tất cả trên trang" xuống hàng hint.** Chuyển nút từ `actions` vào `footer` của `PaneHeader` (footer đã tồn tại), bọc trong `.pf-footrow`:

```tsx
footer={
  <div className="pf-footrow">
    {!fromPaste && (
      <Button variant="link" size="sm" onClick={() => void highlight(items)}>
        <Icon name="locate" size={14} />
        Xem tất cả trên trang
      </Button>
    )}
    <p className="pf-hint">Khi lưu, các đoạn xếp theo thứ tự trong trang.</p>
  </div>
}
```

```css
.pf-footrow { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; }
.pf-footrow .pf-hint { margin: 0; }
```

**(c) Chỉ hiện hint thứ tự lưu khi cần.** Câu "Khi lưu, các đoạn xếp theo thứ tự trong trang." chỉ có nghĩa khi đang sort theo tin cậy (thứ tự hiển thị khác thứ tự lưu):

```tsx
{sort === 'confidence' && <p className="pf-hint">Khi lưu, các đoạn xếp theo thứ tự trong trang.</p>}
```

> Ghi chú: thay đổi này **cũng áp dụng ở ≥721px** (link chuyển từ hàng tiêu đề xuống hàng hint). Đây là đánh đổi để không phải render trùng nút; bố cục rộng vẫn giữ nguyên thứ tự tiêu đề → phụ đề → hành động → hint, chỉ khác link nằm dưới. Nếu muốn giữ tuyệt đối ≥721px, cần thêm một slot `mobileFooter` (không khuyến nghị vì phức tạp hoá API).

**Số đo sau khi dựng thử bằng chính `styles.css` (panel 400px):**

| Phương án | Không banner | Có banner `full_page` |
|---|---|---|
| Hiện tại | 164px | 220px |
| R2a + R2b (sort ngắn, link xuống footer) | 156px | 214px |
| R2a + R2b + R2c (ẩn hint khi sort theo trang) | **136px** | **194px** |
| Thêm `flex: 1 1 120px` cho khối tiêu đề để actions cùng hàng | **119px** | **177px** |

Khuyến nghị áp dụng R2a–R2c (giảm 28px khi không banner, 26px khi có banner, bớt 1 hàng nút). Phương án cuối (`flex-basis` cố định) **không** khuyến nghị mặc định vì ở 320px tiêu đề sẽ bị ép quá hẹp; nếu muốn, chỉ bật trong khoảng `481–720px` và kiểm tra ảnh chụp 320px.

### R3 — Bỏ class chết

```tsx
// PageFinderView.tsx:342
<div>   {/* bỏ className="pf-rail-top" */}
```

Giữ `<div>` để `.pf-composer { margin-top: auto }` vẫn neo đáy rail. Không thêm CSS mới cho class này.

### R4 — Vùng bấm tối thiểu 24px cho sort

```css
.pf-sort button {
  min-height: 24px;
  padding: 4px 10px;   /* 22,7px → ~24,7px */
}
```

### R5 — Bỏ live region bao quanh danh sách nhóm

- `NotesView.tsx:318`: bỏ `aria-live="polite"` khỏi `<div className="note-groups">`. Số lượng đã nằm trong `PaneHeader` subtitle (aria-live polite).
- `PageFinderView.tsx` `PaneHeader` của kết quả: thêm `subtitleLive={false}` — "Thấy N đoạn · đã chọn M" đổi theo từng checkbox, không nên đọc lại; tiến độ quét đã có `role="status"` riêng.

### R6 — Đồng bộ nút thao tác trong nhóm với `.pane-actions`

```css
.source-group-actions .btn-ghost { border-color: transparent; }
.source-group-actions .btn-ghost:hover:not(:disabled) {
  background: var(--surface);
  border-color: transparent;
}
```

Chọn `variant="ghost"` vẫn giữ (không đổi TSX), chỉ làm phẳng viền để header nhóm không bị cạnh tranh thị giác.

### R7 — `aria-controls` cho "Xem thêm"

Cho `GroupSection` nhận id body tuỳ chọn (mặc định vẫn `useId()`):

```tsx
export function GroupSection({ ..., bodyId }: { ...; bodyId?: string }) {
  const autoId = useId()
  const id = bodyId ?? autoId
  ...
  <div id={id} hidden={collapsed}>
```

`SearchResults` truyền `bodyId={`search-group-${key}-body`}` và thêm `aria-controls` cho nút "Xem thêm". Không đổi hành vi, chỉ bổ sung quan hệ điều khiển.

### R8 — Dùng `<section>` cho vùng có tên

```tsx
// SearchResults.tsx
<section className="search-results" aria-label="Kết quả tìm kiếm theo nguồn">
// NotesView.tsx:266
<section aria-label="Kết quả tìm kiếm bằng AI">
```

Khớp pattern hiện có: `<section className="library" aria-label>`, `<section className="pagematch" aria-label>`, `<section className="stack" aria-label="Tìm kiếm ghi chú">`.

### R9 — Token hoá nền "đang chọn" của card

```css
:root { --selected-bg: color-mix(in srgb, var(--accent-soft) 40%, var(--bg)); }
.pf-card.is-selected { background: var(--selected-bg); border-color: var(--accent-soft-border); }
```

Giữ sắc nhẹ cho card lớn (khác `--accent-soft` đậm của hàng note), nhưng màu đi qua token và tự theo light/dark.

### R10 — Căn summary đúng 28px

Đã gộp vào R1 (`margin-left: 28px`).

### R11 — `ScanScopeDialog`: bỏ inline style, autofocus nút chính

```tsx
<div className="stack">
  <p className="modal-lede">
    Nội dung khoảng <strong>{chars.toLocaleString('vi-VN')}</strong> ký tự, ước tính{' '}
    <strong>~{estimateTokens(chars).toLocaleString('vi-VN')}</strong> token hạn mức AI, chia khoảng{' '}
    <strong>{estimateBatches(chars)}</strong> lô xử lý.
  </p>
  <p className="modal-lede">
    {prompt?.source === 'paste' ? 'Nội dung dán' : 'Trang này'} dài hơn {SCAN_WARN_CHARS.toLocaleString('vi-VN')} ký tự…
  </p>
</div>
```

```tsx
<Button onClick={() => onChoose('capped')} data-autofocus>Quét 50k đầu</Button>
```

```css
.manage-lede, .modal-lede { margin: 0; font-size: 12.5px; line-height: 1.6; color: var(--muted); text-wrap: pretty; }
.modal-lede strong { color: var(--fg); font-weight: 650; }
```

`Modal` đã query `[data-autofocus]` trước `input/textarea/select/.modal-body button` (`Modal.tsx:32`) nên nút mặc định sẽ được focus, không cần sửa `Modal`.

### R12 — Refactor `PaneHeader` + gộp CSS pane-head

**API mới** (bỏ 5 prop className, giữ `className` cho layout ngoài):

```tsx
export function PaneHeader({
  title, subtitle, actions, children, footer,
  as: Tag = 'div', className, subtitleLive = true, id,
}: { ... })
```

Markup nội bộ cố định:

```tsx
<Tag className={className || undefined}>
  {children}
  <div className="pane-head-row">
    <div className="pane-heading">
      <h2 className="pane-title">{title}</h2>
      {subtitle != null && subtitle !== '' && (
        <p className="pane-subtitle" aria-live={subtitleLive ? 'polite' : undefined}>{subtitle}</p>
      )}
    </div>
    {actions != null && <div className="pane-actions">{actions}</div>}
  </div>
  {footer}
</Tag>
```

**CSS gộp** (giữ alias `.pf-*` 1 nhịp theo đúng quy ước P5 như `.pf-sim`, `.pane-rail`):

```css
.pane-head-row, .pf-titlerow {
  display: flex; flex-wrap: wrap; align-items: flex-start;
  justify-content: space-between; gap: 4px 12px;
}
.pane-title, .pf-title { margin: 0; font-size: 15px; font-weight: 650; letter-spacing: -0.01em; color: var(--fg-strong); }
.pane-subtitle, .pf-meta { margin: 2px 0 0; font-size: 12px; color: var(--muted); }
.pane-actions, .pf-headactions { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; flex: 0 0 auto; }
.pane-subtitle { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }        /* giữ hành vi cũ */
.pf-head .pane-head-row { padding: 12px 0 10px; }
.pf-head .pane-subtitle { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; white-space: normal; }
```

**Consumer sau refactor:**

```tsx
// NotesView
<PaneHeader className="pane-head" title={…} subtitle={…} actions={…} />

// PageFinderView
<PaneHeader as="header" className="pf-head" title="Kết quả truy vấn" subtitle={…} actions={…} footer={…}>
  {banner}
</PaneHeader>
```

**Kiểm tra hồi quy:** `tests/ui/pane-header.test.tsx` chỉ dựa trên heading/parent/hint nên vẫn xanh; `tests/ui/page-finder.test.tsx` dùng role/text nên không phụ thuộc class. `.pf-titlerow/.pf-title/.pf-meta/.pf-headactions` giữ alias để e2e/ảnh chụp cũ không vỡ.

### R13 — Dùng chung `ProgressBar` cho tiến độ quét

**Mở rộng `State.tsx`:**

```tsx
export function ProgressBar({
  value, max, label, tone, indeterminate = false,
}: {
  value: number
  max: number
  label: string
  /** 'accent' cho tiến trình trung tính (quét trang); bỏ trống = tự chọn theo % như thanh dung lượng. */
  tone?: 'accent' | 'ok' | 'warn' | 'danger'
  indeterminate?: boolean
}) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0
  const auto = pct >= 90 ? 'danger' : pct >= 70 ? 'warn' : 'ok'
  return (
    <div
      className={`progress${indeterminate ? ' is-indeterminate' : ''}`}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={indeterminate ? undefined : max}
      aria-valuenow={indeterminate ? undefined : value}
    >
      <div
        className={`progress-bar progress-${tone ?? auto}`}
        style={indeterminate ? undefined : { width: `${pct}%` }}
      />
    </div>
  )
}
```

**CSS:** thêm `--progress-accent` hoặc dùng `var(--accent)`; chuyển animation indeterminate từ `.pf-progress-track` sang `.progress.is-indeterminate`, giữ khối `prefers-reduced-motion`.

**PageFinderView:**

```tsx
{progress?.phase === 'batch' && progress.total ? (
  <ProgressBar label="Tiến độ quét" value={progress.index ?? 0} max={progress.total} tone="accent" />
) : (
  <ProgressBar label="Tiến độ quét" value={0} max={1} tone="accent" indeterminate />
)}
```

**Xoá** `.pf-progress-track*` và `@keyframes pf-indeterminate` khỏi `styles.css` (không còn consumer).

**Thay đổi thị giác có chủ đích:** thanh 4px không viền → thanh 8px có viền `--border` như thanh dung lượng trong rail chat → đồng bộ với UI đang có.

**Test cần cập nhật/thêm:**
- `tests/ui/page-finder.test.tsx:294` vẫn tìm `role="progressbar"` tên "Tiến độ quét" và `aria-valuenow="2"`/`aria-valuemax="5"` — giữ nguyên hành vi determinate.
- Thêm test `ProgressBar indeterminate` không có `aria-valuenow`.
- `tests/ui/ui.test.tsx:392/446` (dung lượng) phải tiếp tục xanh.

### R14/R15 — Không đổi trong đợt này

- Hai `.composer-hint`: đã đo ở 420/480/520/600/880px — không tràn ở các bề rộng sidepanel thực tế (media query `≤720px` ẩn cả hai). Nếu muốn gọn hơn, gộp thành một dòng và cập nhật `tests/ui/chat.test.tsx:227`; để đợt sau.
- Nhãn uppercase 12px vs 11px: hai cấp thông tin khác nhau (nhóm nguồn vs rail), giữ nguyên.
- Badge "Tóm tắt từ ghi chú": giữ nguyên theo thiết kế P2 (`ux_improvement_plan.md` §5.2).

## 4. Thứ tự thực hiện (stack PR, mỗi PR ≤ ~150 dòng)

| PR | Nội dung | File chính | Phụ thuộc |
|---|---|---|---|
| **PR1** | Fix CSS/visual không đổi cấu trúc: R1, R3, R4, R6, R9, R10 | `styles.css`, `PageFinderView.tsx` (1 dòng) | — |
| **PR2** | `PaneHeader` refactor + gộp CSS + thu gọn header `≤720px` + dialog: R2, R5, R11, R12 | `PaneHeader.tsx`, `PageFinderView.tsx`, `NotesView.tsx`, `styles.css`, `tests/ui/pane-header.test.tsx` | PR1 (cùng file CSS) |
| **PR3** | `ProgressBar` dùng chung + indeterminate + tone: R13 | `State.tsx`, `PageFinderView.tsx`, `styles.css`, `tests/ui/page-finder.test.tsx` | PR2 (header) |
| **PR4** | A11y nhỏ: R7, R8 (+ rà `aria-live` còn lại) | `GroupSection.tsx`, `SearchResults.tsx`, `NotesView.tsx`, `tests/ui/*` | PR2 |

> Nếu cần một PR duy nhất: gộp PR1+PR2 (cùng khu vực CSS/header), giữ PR3 và PR4 riêng để review dễ.

## 5. Tiêu chí nghiệm thu

### Tự động

```bash
cd apps/extension
npm run typecheck
npx vitest run tests/ui tests/chat-sources.test.ts tests/group-notes.test.ts tests/search-summary.test.ts
npm test
npm run build && npm run check:bundle
```

- [ ] `typecheck` sạch.
- [ ] Test UI xanh; số test tăng do test `ProgressBar` indeterminate + `GroupSection` `aria-controls`.
- [ ] `build` + `check:bundle` không tăng bất thường (baseline P5: 11 tệp, ~251 kB).
- [ ] Test bàn phím hiện có vẫn xanh: sort, group header, Modal (Esc/Tab/focus).

### Thủ công (preview dùng `styles.css` thật, hoặc sidepanel thật)

- [ ] 400px, light + dark: header "Tìm trong trang" **≤ ~140px** khi không có banner full_page, **≤ ~200px** khi có banner (hiện 164/220); sort + "Chọn tất cả" cùng 1 hàng; link "Xem tất cả trên trang" nằm hàng hint; hint thứ tự lưu chỉ hiện khi sort "Tin cậy".
- [ ] 320px: tiêu đề "Kết quả truy vấn" không bị cắt/ép (nếu áp dụng `flex-basis` tuỳ chọn, chỉ bật từ 481px).
- [ ] 400px: summary nhóm nằm cùng dòng badge, căn thẳng nhãn nhóm (28px).
- [ ] 400px: "Chọn cả nhóm" không còn viền nổi; hover vẫn có nền `--surface`.
- [ ] Nút sort đo được **≥ 24×24px**; focus-visible rõ.
- [ ] 320px: không tràn ngang ở library, pagematch, composer.
- [ ] 720/880/1024/1440px: không hồi quy bố cục; banner full_page vẫn nằm trên tiêu đề.
- [ ] Keyboard: Tab vào group header → Enter/Space mở/đóng; sort bằng Enter/Space; Esc đóng dialog phạm vi quét; focus trả về nút mở.
- [ ] Screen reader (nếu có): không đọc lại toàn bộ danh sách khi đóng/mở nhóm; "Thấy N đoạn · đã chọn M" không bị đọc mỗi lần tick.

### E2E (khi có môi trường Docker/Postgres/Playwright)

- [ ] `c05-library` (region "Nguồn …", Chọn/Chuyển thư mục, dialog).
- [ ] `r05-search` (`ol.list > li`, "Mở ghi chú", "Mở trang nguồn").
- [ ] `ux-screens` (ảnh chụp sẽ đổi ở header page-match — chấp nhận và cập nhật baseline).
- [ ] `h05-a11y` (axe + tab/Enter/Escape).

## 6. Rủi ro & cách giảm

| Rủi ro | Giảm thiểu |
|---|---|
| Refactor class `.pf-*` → `.pane-*` làm vỡ e2e/ảnh chụp | Giữ alias CSS 1 nhịp (đúng quy ước P5); e2e hiện dùng role/text, không dùng các class này |
| `PaneHeader` đổi API làm vỡ consumer ngoài 2 màn | Chỉ có 2 consumer; cập nhật cùng PR, `grep PaneHeader` xác nhận |
| ProgressBar đổi hình thức thanh quét | Ghi rõ trong PR; test determinate giữ nguyên; so ảnh trước/sau |
| Nhãn sort ngắn mất ngữ nghĩa | `aria-label` đầy đủ + `title`; nhãn dài vẫn hiện ≥721px |
| Live region bị bỏ làm mất thông báo số kết quả | Số kết quả đã nằm ở PaneHeader subtitle (`aria-live`), giữ nguyên |

## 7. Ngoài phạm vi (ghi nhận, không làm đợt này)

- Semantics "Nguồn (N)" trong Hỏi AI đang đếm **số domain**, không phải số nguồn/chip — cần quyết định sản phẩm, không phải style.
- `Tabs` (accent fill) và `.pf-sort` (segmented pill) là hai pattern chọn khác nhau; giữ vì khác vai trò (điều hướng vs lọc).
- Hợp nhất 2 dòng hint ở composer (R14).
- `.pf-title` có thể cần ellipsis khi tiêu đề dài; chưa xử lý vì tiêu đề hiện là chuỗi cố định.
- Chưa chạy e2e/axe trên sidepanel thật trong môi trường hiện tại (thiếu Docker/Postgres/Playwright chromium).
