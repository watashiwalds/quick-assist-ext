# Nguồn chi tiết cho ghi chú — Kế hoạch triển khai

> **Trạng thái:** Kế hoạch chi tiết, chờ triển khai  
> **Ngày:** 2026-11-20  
> **Phạm vi:** `apps/extension` (chính); backend không đổi contract, không migration  
> **Liên quan:** ADR-0015 (nguồn dán), ADR-0018 (đề xuất — nguồn chi tiết theo raw URL)  
> **Ước lượng thô:** 4–5 người-ngày

## 0. TL;DR

1. **Nguồn khi dán:** lấy tab đang mở làm **nguồn tham chiếu** (URL + title), hiện chip cho sửa/bỏ/nhập tay; truyền `url`/`title` qua `pageMatch/run` và lưu vào note. API `PageMatchIn` đã hỗ trợ sẵn hai trường này cho nguồn `text`, nên **không cần đổi backend**.
2. **Gom nhóm theo nguồn chi tiết:** key = **raw URL bỏ `?query` và `#hash`** (`origin + pathname`). Không strip `www.`, không xử lý AMP/mobile, không sort query, không danh sách tracking param.
3. **Cả 3 nơi:** Thư viện nhóm phẳng theo trang + toggle “Trang / Trang web”; Tìm kiếm và Hỏi AI giữ nhóm domain hiện có, thêm **nhóm con theo trang**.
4. **Backend vẫn gom theo domain** để xếp hạng/truy xuất. Trang là tầng nhóm hiển thị ở client. Nhờ vậy không sửa `source_index`, prompt RAG, API contract hay chat history cũ; vẫn giữ đa dạng nguồn trong tìm kiếm.
5. **Không thêm quyền**, không đọc clipboard tự động, không migration, không đổi `Note.title` (vẫn là truy vấn với Page Finder).

## 1. Mục tiêu

1. Ghi chú tạo từ nội dung dán có thể mang nguồn tham chiếu là tab đang mở, với một thao tác duy nhất và luôn sửa/bỏ được.
2. Thư viện phân biệt được **từng bài/trang** trong cùng một domain, không chỉ gom theo `vnexpress.net`.
3. Tìm kiếm và Hỏi AI cho thấy cấu trúc **domain → trang → ghi chú** mà không làm giảm số domain đa dạng trong top nguồn.
4. Không tăng permission, không migration, không thay đổi hành vi backend/RAG hiện có.
5. Có test tự động cho các quy tắc URL, luồng dán, nhóm Thư viện, nhóm con Tìm kiếm/Hỏi AI.

### Không phải mục tiêu

- Không đổi backend sang page-level grouping, không đổi `source_index`, không đổi prompt `<source>`.
- Không thêm `tabs` permission hay `clipboardRead`.
- Không tự động đọc clipboard; người dùng vẫn Ctrl+V.
- Không thêm cột `source_title` hay migration note cũ.
- Không đổi tiêu đề note từ truy vấn sang tiêu đề bài.
- Không giải quyết triệt để URL dạng `?id=123` / `?p=123` (xem Rủi ro).

## 2. Quyết định đã chốt

| # | Vấn đề | Quyết định |
|---|---|---|
| D1 | Nguồn khi dán | Tự lấy tab đang mở làm **nguồn tham chiếu**; chip cho sửa/bỏ/nhập URL tay |
| D2 | Quyền lấy URL tab | Dùng `activeTab` + optional host hiện có; thiếu URL thì nhập tay, **không thêm `tabs`** |
| D3 | Định danh nguồn chi tiết | Raw URL bỏ `?query` và `#hash`; giữ nguyên scheme/host/path |
| D4 | URL dạng `?id=` | Giữ đúng raw URL, chấp nhận rủi ro gộp nhầm; không thêm ngoại lệ path generic trong MVP |
| D5 | Phạm vi hiển thị | Cả Thư viện, Tìm kiếm, Hỏi AI |
| D6 | Backend grouping | Giữ domain-level; page grouping chỉ ở client |
| D7 | Toggle Trang/Trang web | Nhớ trong `Preferences`, mặc định `page` |
| D8 | Nhãn trang ở Hỏi AI | Chỉ trong “Chi tiết nguồn”, chip vẫn gọn theo domain |
| D9 | Tiêu đề note Page Finder | Giữ nguyên = truy vấn |
| D10 | Migration | Không migration; note cũ fallback domain/unknown |

## 3. Hiện trạng và khoảng trống

### 3.1. Nguồn khi dán

- `apps/extension/src/background/page-match.ts:121-127`: nhánh `text` gửi `{ query, text, url: null, scan_all }`; kết quả trả `url: null, title: null`.
- `apps/api/src/quickassist/presentation/schemas/page_match.py:19-20`: `PageMatchIn` đã có `url`/`title`, chỉ là metadata.
- `apps/api/src/quickassist/business/notes/notes_service.py:137-139, 178-185`: `Note.url` được lưu đầy đủ; `domain` tự suy từ hostname.
- `apps/extension/src/ui/features/page-finder/PageFinderView.tsx:275-287`: lưu note bằng `result.url ?? null`; nguồn dán hiện không có URL nên mất nguồn.
- `apps/extension/manifest.config.ts:22-29`: chỉ có `activeTab` + optional host; không có `tabs`.

**Khoảng trống:** không có bước lấy tab hiện tại, không có UI chọn/bỏ nguồn, không truyền `url`/`title` cho nhánh text.

### 3.2. Gom nhóm Thư viện

- `apps/extension/src/ui/features/notes/groupNotes.ts:51-107`: gom theo `document_id ?? domain`; note không domain vào “Không rõ nguồn”.
- `NotesView.tsx:92-100`: gọi `groupNotesBySource(list)` không có chế độ.
- `GroupSection.tsx:40-55`: header chỉ có label + count, chưa có link nguồn.

**Khoảng trống:** không phân biệt hai bài cùng domain; không có toggle; nhãn domain bị uppercase nên không phù hợp để hiện path.

### 3.3. Tìm kiếm và Hỏi AI

- `SearchResults.tsx:12`: `sourceKey = s.domain ?? '__unknown__'`; mỗi domain là một `GroupSection`.
- `Sources.tsx:25-39`: `groupChatSources` gom theo `source_index` (domain), chưa có nhóm con.
- `SearchNoteOut.url` và `ChatSource.url` đều đã có URL của note → đủ dữ liệu để nhóm trang ở client.
- `SearchSourceOut.note_count` là count theo domain; `ChatSource.source_index` là hạng domain.

**Khoảng trống:** chưa có nhóm con theo trang; `sourceKey` của Search có thể trùng React key khi hai tài liệu cùng domain.

## 4. Kiến trúc

```
┌──────────────────────────── Extension (client) ────────────────────────────┐
│                                                                            │
│  PageFinder (paste mode)                                                   │
│    │  pageMatch/source ──► background.getActiveTabSource()                  │
│    │                         └─ chrome.tabs.query (activeTab/optional host) │
│    │                                                                        │
│    └─ pageMatch/run { query, text, url?, title? }                          │
│          │                                                                  │
│          └─► API /ai/page-match/stream  (không đổi contract)               │
│                 └─ log metadata; không dùng url để highlight                │
│                                                                            │
│  notes/create { url } ──► API /notes (không đổi) ──► Note.url + Note.domain │
│                                                                            │
│  Note.url / SearchNoteOut.url / ChatSource.url                             │
│    │                                                                        │
│    └─ shared/source.ts: sourceKey(url) = origin + pathname                 │
│          ├─ Library: groupNotesBySource(notes, 'page' | 'site')             │
│          ├─ Search: groupByPage(source.notes) trong từng domain             │
│          └─ Chat: groupByPage(group.notes) trong từng domain                │
└────────────────────────────────────────────────────────────────────────────┘
```

**Nguyên tắc:** backend vẫn là nguồn chân lý cho domain-level retrieval; client là nguồn chân lý cho cách hiển thị trang. Không có API mới, không migration.

## 5. Quy tắc nguồn chi tiết

### 5.1. `sourceKey(url)`

```ts
// apps/extension/src/shared/source.ts
export function sourceKey(raw: string | null | undefined): string | null {
  if (!raw) return null
  try {
    const u = new URL(raw.trim())
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null
    // Bỏ query + hash; giữ nguyên scheme/host/path (kể cả dấu "/" cuối).
    return `${u.protocol}//${u.host}${u.pathname}`
  } catch {
    return null
  }
}
```

Ví dụ:

| Input | `sourceKey` |
|---|---|
| `https://vnexpress.net/bai-bao?utm_source=x#top` | `https://vnexpress.net/bai-bao` |
| `https://vnexpress.net/bai-bao/` | `https://vnexpress.net/bai-bao/` |
| `https://www.a.vn/x?fbclid=1` | `https://www.a.vn/x` |
| `https://a.vn/article?id=123` | `https://a.vn/article` |
| `https://a.vn/article?id=456` | `https://a.vn/article` |
| `chrome://extensions` | `null` |
| `file:///C:/a.pdf` | `null` |
| `null` / `''` | `null` |

**Hệ quả đã chấp nhận:** hai bài dùng query làm ID sẽ vào cùng nhóm; `www.` và không `www.` là hai nguồn khác nhau; `/x` và `/x/` là hai nguồn khác nhau. Đây là tradeoff của lựa chọn “raw URL, bỏ modifier”.

### 5.2. `sourceDomain` và `sourceLabel`

```ts
export function sourceDomain(raw: string | null | undefined): string | null {
  if (!raw) return null
  try {
    const u = new URL(raw.trim())
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null
    return u.hostname // lowercase theo URL parser; giữ www nếu có
  } catch {
    return null
  }
}

export function sourceLabel(raw: string | null | undefined, max = 80): string | null {
  const key = sourceKey(raw)
  if (!key) return null
  const u = new URL(key)
  const path = decodeURIComponent(u.pathname)
  const label = `${u.host}${path === '/' ? '' : path}`
  return label.length > max ? `${label.slice(0, max - 1)}…` : label
}
```

- `sourceLabel` dùng cho header nhóm, link “Mở trang nguồn”, reader.
- Nếu `decodeURIComponent` lỗi, fallback `u.pathname` (không decode).
- `sourceDomain` dùng cho fallback khi note không có URL và cho toggle “Trang web”.

### 5.3. `groupByPage(items)`

```ts
export interface PageGroup<T> {
  key: string
  url: string | null
  label: string
  items: T[]
}

export function groupByPage<T extends { url: string | null }>(items: T[]): PageGroup<T>[] {
  const groups = new Map<string, PageGroup<T>>()
  for (const item of items) {
    const key = sourceKey(item.url) ?? '__unknown_page__'
    const group = groups.get(key)
    if (group) group.items.push(item)
    else groups.set(key, {
      key,
      url: key === '__unknown_page__' ? null : item.url,
      label: sourceLabel(item.url) ?? 'Không rõ trang',
      items: [item],
    })
  }
  return [...groups.values()]
}
```

- Giữ thứ tự xuất hiện (Map insertion) để không phá thứ hạng relevance của Search/Chat.
- “Không rõ trang” luôn nằm cuối trong từng domain group.

## 6. UX chi tiết

### 6.1. Chế độ dán — nguồn tham chiếu

**Trạng thái có nguồn:**

```
┌ Nguồn tham chiếu ──────────────────────────────┐
│ [icon link] Quyền lực Nvidia ra sao…           │
│             vnexpress.net/kinh-doanh/...       │
│                         [Lấy lại tab] [Bỏ]     │
└────────────────────────────────────────────────┘
```

**Trạng thái không lấy được URL:**

```
Chưa gắn nguồn. [Lấy từ tab hiện tại] [Nhập URL]
```

- Nhãn dùng **“Nguồn tham chiếu”**, không dùng “Nguồn”, để không khẳng định text được copy từ tab đó.
- Vào chế độ dán → thử lấy tab hiện tại một lần.
- `onPaste` → nếu chưa có source thì thử lấy tab; không ghi đè source người dùng đã sửa.
- “Bỏ” → source = null; quét/lưu không URL.
- “Nhập URL” → input `type="url"`, validate `http/https`, tối đa 2048 ký tự; title để trống.
- “Lấy lại tab hiện tại” → gọi lại `pageMatch/source`, cập nhật chip.
- Khi quét: gửi `url`/`title` nếu có.
- Khi lưu: nguồn dán dùng `source?.url ?? null`; nguồn trang dùng `result.url`.
- Kết quả có link “Mở trang nguồn” nếu có URL.
- “Xem trên trang” vẫn disabled; tooltip: *“Nội dung dán không có trang gốc để xem; nguồn tham chiếu chỉ để mở lại bài.”*

### 6.2. Thư viện

- Toggle segmented cạnh bộ lọc thư mục:

```
Gom theo: [ Trang ] [ Trang web ]
```

- Mặc định **Trang**; lưu vào `Preferences.groupNotesBy`.
- Header nhóm trang: `vnexpress.net/kinh-doanh/...` (không uppercase), count “N ghi chú”, link external.
- Header nhóm domain (khi toggle Trang web): `vnexpress.net` như cũ.
- Tài liệu nhiều part: vẫn 1 nhóm, label ưu tiên title; count “N phần”.
- “Không rõ nguồn”/“Không rõ trang” luôn cuối.
- Filter nhanh tìm cả `url` (path) ngoài title/content/domain.
- Reader: link nguồn hiển thị `sourceLabel(note.url)` thay vì chỉ domain; title attribute là URL đầy đủ.

### 6.3. Tìm kiếm

```
▼ vnexpress.net · 4 ghi chú
   ┌ vnexpress.net/kinh-doanh/bai-a · 2 ghi chú
   │  [note] [note]
   ┌ vnexpress.net/the-thao/bai-b · 2 ghi chú
   │  [note] [note]
   [Xem thêm 6 ghi chú]
```

- Domain `GroupSection` giữ nguyên count `note_count` và “Xem thêm”.
- Trong domain, nhóm `s.notes` bằng `groupByPage`.
- Chỉ hiện header trang khi domain có > 1 trang; nếu 1 trang thì ẩn để giảm nhiễu.
- “Không rõ trang” cuối domain.
- Sửa `sourceKey` React key: `s.document_id ?? s.domain ?? '__unknown__'`.

### 6.4. Hỏi AI

- Chip nguồn vẫn nhóm theo domain, không đổi.
- “Chi tiết nguồn”:

```
▼ vnexpress.net · 4 ghi chú · 2 trang
   ┌ vnexpress.net/kinh-doanh/bai-a · 2 ghi chú
   │  [source card] [source card]
   ┌ vnexpress.net/the-thao/bai-b · 2 ghi chú
   │  [source card] [source card]
```

- Nhãn trang chỉ trong detail; chip giữ gọn.
- Chat history cũ: source thiếu `url` → một nhóm “Không rõ trang”, ẩn header nếu chỉ 1 trang; không crash.

## 7. Thay đổi kỹ thuật

### 7.1. Shared utility (mới)

**File:** `apps/extension/src/shared/source.ts`

- `sourceKey`, `sourceDomain`, `sourceLabel`, `groupByPage`.
- Type `SourceRef = { url: string; title: string; kind: 'tab' | 'manual' }` (dùng cho PageFinder).
- Không import React, không I/O → test thuần.

**Test:** `apps/extension/tests/source.test.ts`

- Bảng URL ở §5.1.
- Query/hash bị bỏ; path giữ nguyên; protocol invalid → null.
- `groupByPage` giữ thứ tự, gộp URL trùng, unknown cuối.
- `sourceLabel` cắt đúng độ dài, path `/` chỉ còn host.

### 7.2. Background + protocol

**File:** `apps/extension/src/background/page-match.ts`

```ts
export async function getActiveTabSource(): Promise<{ url: string; title: string } | null> {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
  const url = tab?.url
  if (!url || !/^https?:/.test(url)) return null
  return { url, title: (tab.title ?? '').slice(0, 500) }
}
```

- `RunArgs` thêm `url?: string`, `title?: string`.
- Nhánh text:

```ts
const result = await streamMatch(
  { query, text, url: url ?? null, title: title ?? null, scan_all: scanAll },
  requestId,
)
return { ...result, url: url ?? null, title: title ?? null }
```

**File:** `apps/extension/src/shared/messaging/protocol.ts`

- `Preferences` thêm `groupNotesBy: 'page' | 'site'`.
- `PageMatchRun` comment: nguồn dán có thể có `url`/`title` tham chiếu; `tabId` vẫn chỉ có khi nguồn là trang.
- `RpcMap` thêm:

```ts
'pageMatch/source': { req: void; res: { url: string; title: string } | null }
```

**File:** `apps/extension/src/background/handlers.ts`

- Import `getActiveTabSource`.
- Thêm handler `'pageMatch/source': () => getActiveTabSource()`.

**Test:** `apps/extension/tests/page-match.test.ts`

- Text branch gửi `url`/`title` khi có, gửi null khi không.
- `getActiveTabSource` trả null với `chrome://`, `file://`, tab không có URL.
- Trang thường vẫn giữ nguyên hành vi.

### 7.3. PageFinder UI

**File:** `apps/extension/src/ui/features/page-finder/PageFinderView.tsx`  
**Component mới (khuyến nghị):** `apps/extension/src/ui/features/page-finder/SourceChip.tsx`

- State:

```ts
const [source, setSource] = useState<SourceRef | null>(null)
```

- `captureTabSource()`: gọi `rpc('pageMatch/source')`, bọc `catch` im lặng; nếu có thì set `{ ...s, kind: 'tab' }`.
- `useEffect` khi `pasteMode` bật: nếu `source === null` thì capture.
- `onPaste` của textarea: nếu `source === null` thì capture.
- `SourceChip` props: `source`, `onCapture`, `onClear`, `onManual`.
- Manual URL: input + nút “Dùng URL”; validate bằng `sourceKey`; nếu invalid hiện lỗi inline.
- `scan` truyền `url: source?.url`, `title: source?.title`.
- `save` dùng:

```ts
const url = result.tabId == null ? (source?.url ?? null) : (result.url ?? null)
```

- Kết quả: thêm dòng “Nguồn tham chiếu: …” + link external; chỉ khi `source` có URL.
- Không đổi `fromPaste = result.tabId == null`.
- Không đổi title lưu note (`title = query`).

**Test:** `apps/extension/tests/ui/page-finder.test.tsx`

- Vào paste mode → gọi `pageMatch/source`; chip hiện title/URL.
- Bỏ chip → `pageMatch/run` không có `url`; `notes/create.url = null`.
- Nhập URL tay → `pageMatch/run` và `notes/create` nhận URL.
- URL invalid → chặn quét/lưu với thông báo.
- “Xem trên trang” vẫn disabled; tooltip mới.
- Kết quả có “Mở trang nguồn” khi có source.

### 7.4. Thư viện

**File:** `apps/extension/src/ui/features/notes/groupNotes.ts`

```ts
export type SourceGrouping = 'page' | 'site'

export interface NoteSourceGroup {
  key: string
  url: string | null
  domain: string | null
  label: string
  kind: 'document' | 'page' | 'site'
  notes: Note[]
  entries: NoteEntry[]
  summary: string | null
}

export function groupNotesBySource(
  notes: Note[],
  grouping: SourceGrouping = 'page',
): NoteSourceGroup[]
```

Thuật toán:

1. Note có `document_id` → gom theo document như hiện tại; `url = sourceKey(entry.note.url)`; label = title || `sourceLabel(url)` || domain || UNKNOWN.
2. Note không document:
   - `pageKey = sourceKey(n.url)`
   - `domain = n.domain?.trim() || sourceDomain(n.url)`
   - Nếu `grouping === 'page' && pageKey` → key = `pageKey`, kind = `page`.
   - Nếu `grouping === 'site' && domain` → key = `site:${domain}`, kind = `site`.
   - Nếu không có URL nhưng có domain → key = `site:${domain}`, kind = `site` (fallback).
   - Còn lại → key = `__unknown__`, kind = `site`, domain = null.
3. Label:
   - page: `sourceLabel(url) ?? domain ?? UNKNOWN`
   - site: `domain ?? UNKNOWN`
   - document: title || `sourceLabel(url)` || domain || UNKNOWN
4. Sort: unknown cuối; nhiều entry trước; mới nhất trước; label.

**File:** `apps/extension/src/ui/features/notes/NotesView.tsx`

- Props mới (optional để không phá test cũ):

```ts
groupNotesBy?: SourceGrouping
onGroupNotesByChange?: (value: SourceGrouping) => void
```

- Fallback local state nếu không truyền props.
- `groupNotesBySource(list, grouping)`.
- Filter `hit`: thêm `n.url`.
- Toggle segmented trong `.pane-tools`.
- `GroupSection` nhận `sourceUrl={g.url}` và `labelKind={g.kind}`.
- `ariaLabel`: document `Tài liệu …`, page `Trang …`, site `Nguồn …`.

**File:** `apps/extension/src/ui/components/GroupSection.tsx`

- Props thêm:

```ts
sourceUrl?: string | null
labelKind?: 'document' | 'page' | 'site'
```

- Render link external cạnh label (ngoài button toggle), `aria-label="Mở trang nguồn"`, `target="_blank"`, `rel="noreferrer noopener"`.
- Class `is-page` cho label để bỏ uppercase/letter-spacing.

**File:** `apps/extension/src/ui/features/notes/NoteReader.tsx`

- Link nguồn: `sourceLabel(note.url) ?? note.domain ?? 'nguồn'`.
- `title={note.url}` để xem URL đầy đủ.

**File:** `apps/extension/src/ui/sidepanel/App.tsx`

- Truyền:

```tsx
<NotesView
  ...
  groupNotesBy={prefs.data?.groupNotesBy ?? 'page'}
  onGroupNotesByChange={(value) => {
    void rpc('prefs/set', { groupNotesBy: value }).then((p) => prefs.setData(p))
  }}
/>
```

**File:** `apps/extension/src/background/prefs.ts`

- `DEFAULTS` thêm `groupNotesBy: 'page'`.
- `getPrefs` sanitize:

```ts
const groupNotesBy = v?.groupNotesBy === 'site' ? 'site' : 'page'
return { ...DEFAULTS, ...v, groupNotesBy }
```

**Test:**

- `tests/group-notes.test.ts`: page mode, site mode, URL variants, document ưu tiên, unknown cuối, note không URL fallback domain.
- `tests/ui/ui.test.tsx`: toggle gọi `prefs/set`; page groups; site groups; reader link label.
- `tests/quick-note.test.ts`: prefs mặc định vẫn đúng (không bắt buộc nếu `getPrefs` merge).

### 7.5. Tìm kiếm

**File:** `apps/extension/src/ui/features/search/SearchResults.tsx`

- `sourceKey(s) = s.document_id ?? s.domain ?? '__unknown__'`.
- Trong mỗi domain:

```ts
const visible = open ? s.notes : s.notes.slice(0, INITIAL_NOTES)
const pages = groupByPage(visible)
```

- Render:
  - Nếu `pages.length <= 1`: giữ nguyên danh sách note như cũ (không thêm header trang).
  - Nếu > 1: mỗi page là một `<section className="source-page">` với header `page.label` + count, bên trong `<ol className="list hit-list">`.
- “Xem thêm” vẫn ở cấp domain; khi mở rộng, page groups được tính lại.
- Note không URL → “Không rõ trang” cuối.

**Test:** `tests/ui/ui.test.tsx` (hoặc tách `search-results.test.tsx`)

- 4 note cùng domain, 2 URL → 2 page subgroups.
- 1 URL → không hiện header trang.
- Note không URL → “Không rõ trang” cuối.
- Hai document cùng domain → không trùng React key, không mất nhóm.
- “Xem thêm” vẫn hoạt động.

### 7.6. Hỏi AI

**File:** `apps/extension/src/ui/features/chat/Sources.tsx`

- Type mới:

```ts
export interface ChatSourcePage {
  key: string
  url: string | null
  label: string
  notes: ChatSource[]
}

export interface ChatSourceGroup {
  key: string
  domain: string | null
  label: string
  notes: ChatSource[]
  pages: ChatSourcePage[]
}
```

- `groupChatSources`:
  - Giữ gom theo `source_index` / `source_domain` như hiện tại.
  - Sau khi có `notes`, `pages = groupByPage(notes)`.
  - Page label `sourceLabel(url) ?? 'Không rõ trang'`.
- `Sources` detail:
  - Trong mỗi domain `<li>`, render từng page.
  - Chỉ hiện header page khi `pages.length > 1`.
  - Domain count có thể thêm `· M trang` khi > 1.
- Chip giữ nguyên; không thêm nhãn trang.

**Test:** `tests/ui/chat.test.tsx`, `tests/chat-sources.test.ts`

- 4 source cùng `source_index`, 2 URL → 2 page groups.
- Source cũ không `url` → “Không rõ trang”, không crash.
- Chip vẫn nhóm theo domain; “Nguồn (N)” không đổi.
- Detail hiện page header khi > 1 trang.

### 7.7. CSS

**File:** `apps/extension/src/ui/styles.css`

- `.source-group-label.is-page`: bỏ `text-transform: uppercase`, giảm letter-spacing.
- `.source-group-link`: icon link nhỏ, màu muted, hover rõ.
- `.source-page`: margin/padding nhẹ, border-left hoặc divider.
- `.source-page-head`: flex, label ellipsis, count muted.
- `.paste-source`: chip layout, URL ellipsis, actions.
- Đảm bảo contrast và focus-visible theo pattern hiện có.

### 7.8. Docs / ADR

- Cập nhật `docs/adr/0015-page-match-pasted-text-source.md`:
  - Điểm 6: nguồn dán **có thể** kèm `url` tham chiếu; `url` vẫn chỉ metadata, không dùng highlight.
  - Hệ quả: bỏ câu “nguồn dán gửi url = null”; thêm ghi chú “nguồn tham chiếu có thể sai, UI cho sửa/bỏ”.
- Tạo `docs/adr/0018-detailed-source-attribution.md` (đề xuất):
  - Quyết định raw URL bỏ query/hash.
  - Domain vẫn là đơn vị retrieval.
  - Page grouping ở client cho cả 3 nơi.
  - Không thêm permission/migration.
- Cập nhật `docs/user-guide.md`: cách gắn/bỏ nguồn khi dán; toggle Trang/Trang web.
- Cập nhật `docs/ux/README.md`: luồng “Dán nội dung” + nhóm nguồn chi tiết.
- Ghi chú vào `docs/plan/page-paste/plan.md`: thay đổi so với MVP ban đầu (nguồn dán có URL tham chiếu).

## 8. Kế hoạch triển khai

| Phase | Nội dung | File chính | Test | Ước lượng | Exit criteria |
|---|---|---|---|---|---|
| **P0** | Shared source utility | `src/shared/source.ts` | `tests/source.test.ts` | 0.5 ngày | Bảng URL §5.1 pass; `groupByPage` ổn định |
| **P1** | Nguồn khi dán | `page-match.ts`, `protocol.ts`, `handlers.ts`, `PageFinderView.tsx`, `SourceChip.tsx` | `page-match.test.ts`, `ui/page-finder.test.tsx` | 1 ngày | Chip, bỏ, nhập tay, lưu URL, tooltip |
| **P2** | Thư viện | `groupNotes.ts`, `NotesView.tsx`, `GroupSection.tsx`, `NoteReader.tsx`, `prefs.ts`, `App.tsx` | `group-notes.test.ts`, `ui/ui.test.tsx` | 1 ngày | Page/site toggle, prefs, link nguồn, document giữ nguyên |
| **P3** | Tìm kiếm | `SearchResults.tsx`, `styles.css` | `ui/ui.test.tsx` | 0.5 ngày | Page subgroups, unknown cuối, không trùng key |
| **P4** | Hỏi AI | `Sources.tsx`, `styles.css` | `chat.test.tsx`, `chat-sources.test.ts` | 0.5 ngày | Page subgroups trong detail, chip không đổi |
| **P5** | Docs/ADR + QA | ADR, user guide, UX docs | — | 0.5–1 ngày | Tài liệu khớp hành vi; QA matrix pass |

**Thứ tự:** P0 → P1 → P2 → P3 → P4 → P5. P3/P4 có thể làm song song sau P0 vì chỉ phụ thuộc utility.

## 9. Kiểm thử

### 9.1. Unit

- `sourceKey`: query/hash, protocol, invalid, trailing slash, `www`, query-ID.
- `sourceLabel`: path dài, path `/`, decode lỗi.
- `groupByPage`: thứ tự, gộp URL, unknown cuối.
- `groupNotesBySource`: page/site, document ưu tiên, fallback domain, unknown cuối.
- `groupChatSources`: page groups, old source không URL.

### 9.2. UI

- PageFinder: chip, bỏ, nhập URL, invalid URL, scan payload, save payload, tooltip.
- NotesView: toggle, prefs, group headers, link nguồn, filter theo URL.
- SearchResults: page subgroups, “Xem thêm”, document cùng domain.
- Sources: page subgroups trong detail, chip domain, old history.

### 9.3. Manual QA matrix

| # | Kịch bản | Kỳ vọng |
|---|---|---|
| 1 | Copy từ bài VnExpress đang mở → dán | Chip đúng title/URL; lưu note có URL; Thư viện nhóm theo path |
| 2 | Copy từ Word/PDF khi tab VnExpress đang mở | Chip VnExpress; bỏ chip → lưu không URL; không silent |
| 3 | Copy từ tab khác rồi quay lại tab nguồn | Capture tại thời điểm dán; sửa/bỏ được |
| 4 | Tab `chrome://extensions` | Không có URL; nhập tay hoạt động |
| 5 | Hai bài cùng domain | Page mode tách 2 nhóm; site mode gộp 1 nhóm |
| 6 | Cùng bài với `?utm_*` và `#hash` | Cùng nhóm |
| 7 | `?id=123` và `?id=456` | Cùng nhóm (known limitation) |
| 8 | Search 5 nguồn cùng domain | Domain group + page subgroups; “Xem thêm” đúng |
| 9 | Chat cũ không có URL | “Không rõ trang”, không crash |
| 10 | Tài liệu nhiều part | 1 nhóm, “N phần”, link nguồn đúng |
| 11 | Toggle rồi đóng/mở side panel | Giữ lựa chọn nhờ prefs |
| 12 | Note không URL/domain | “Không rõ nguồn” cuối |

### 9.4. Lệnh kiểm tra

```bash
cd apps/extension
npm run test
npm run typecheck
npm run build

cd ../api
pytest
ruff check .
```

## 10. Acceptance Criteria

- [ ] Dán nội dung từ tab đang mở → chip nguồn hiện URL/title; bỏ chip → lưu không URL; nhập URL tay → lưu đúng URL.
- [ ] `pageMatch/run` nhận `url`/`title` cho nguồn text; `PageMatchRun` trả lại đúng; backend không đổi.
- [ ] Ghi chú nguồn dán có `url`; Thư viện nhóm dưới đúng path; “Mở trang nguồn” hoạt động.
- [ ] “Xem trên trang” vẫn disabled với nguồn dán; tooltip giải thích đúng.
- [ ] Thư viện: page mode tách bài cùng domain; site mode gộp domain; tài liệu nhiều part vẫn 1 nhóm; unknown cuối.
- [ ] Toggle “Trang / Trang web” được lưu vào prefs và khôi phục khi mở lại.
- [ ] Tìm kiếm/Hỏi AI: domain group có page subgroup; note cùng URL nằm cùng trang; source cũ không URL/không `source_index` không crash.
- [ ] Không thêm permission trong manifest; không migration; không đổi prompt/RAG.
- [ ] Test/typecheck/build/lint liên quan đều xanh; QA matrix pass.

## 11. Rủi ro và giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Tab đang mở không phải nguồn thật của text dán | Trung bình | Nhãn “Nguồn tham chiếu”, chip sửa/bỏ; không tự động khẳng định |
| Không lấy được URL do thiếu quyền | Trung bình | Fallback nhập tay; không thêm `tabs`; không tự xin quyền |
| URL `?id=` bị gộp nhầm | Trung bình | Đã chấp nhận (D4); ghi rõ trong docs; xử lý sau nếu gặp thực tế |
| `www`/trailing slash tách nhóm | Thấp | Đã chấp nhận theo raw URL; có thể thêm rule sau |
| Search/Chat chỉ trả N note/domain → page subgroup thiếu note | Thấp | Count domain vẫn đúng; page subgroup là “đã tải”; không đổi backend |
| Trùng React key ở Search khi 2 document cùng domain | Thấp | Sửa `sourceKey` dùng `document_id` |
| Nhãn path bị uppercase, khó đọc | Thấp | `labelKind='page'` + CSS |
| Prefs cũ thiếu `groupNotesBy` | Thấp | `getPrefs` merge default + sanitize |
| Chat history cũ thiếu `url` | Thấp | Fallback “Không rõ trang”, ẩn header nếu 1 trang |
| Note.title là truy vấn, không phải tiêu đề bài | Thấp | Nhãn nhóm dùng path; `source_title` để future |

## 12. Not Doing (và lý do)

- **Backend page-level grouping / đổi `source_index` / prompt RAG** — giữ đa dạng nguồn, tránh sửa contract và chat history; page grouping là chuyện hiển thị.
- **Thêm quyền `tabs`** — trái nguyên tắc quyền tối thiểu; thiếu URL thì nhập tay.
- **Tự đọc clipboard / `clipboardRead`** — Ctrl+V là thao tác chủ động; không cần permission.
- **Canonicalize tracking/www/AMP/trailing slash** — theo lựa chọn mới: chỉ bỏ query/hash.
- **Ngoại lệ path generic cho `?id=`** — giữ đúng raw URL; ghi nhận rủi ro.
- **Thêm `source_title` vào DB** — nhãn nhóm dùng path; nếu cần tiêu đề bài mới thêm.
- **Đổi `Note.title` từ truy vấn sang tiêu đề bài** — giữ hành vi Page Finder hiện tại.
- **Migration note cũ** — note cũ tự fallback domain/unknown; không đụng dữ liệu.
- **Nhãn trang trên chip Hỏi AI** — chỉ trong “Chi tiết nguồn” theo lựa chọn.

## 13. Việc để sau (future)

1. **`source_title`**: lưu tiêu đề bài/trang để nhãn nhóm dễ đọc hơn path; cần migration + API.
2. **Backend `source_url`**: nếu cần API trả page-level source thật, thêm `source_url` vào `SearchSourceOut`/`ChatSource`, ranking có cap trang/domain.
3. **Query-ID guard**: nếu QA thực tế gặp nhiều site `?id=`, thêm ngoại lệ “path generic → giữ query”.
4. **Canonicalize `www`/slash/AMP**: nếu dữ liệu thực tế bị tách nhóm nhiều.
5. **Nhãn trang trên chip Chat**: nếu người dùng cần thấy ngay, thêm badge nhỏ.

## 14. Definition of Done

- [ ] P0–P5 hoàn thành; code review nội bộ.
- [ ] `npm run test`, `npm run typecheck`, `npm run build` xanh.
- [ ] `pytest`, `ruff check .` xanh (backend không đổi nhưng chạy regression).
- [ ] Không có thay đổi `manifest.config.ts` về permissions.
- [ ] ADR-0015 cập nhật + ADR-0018 thêm mới.
- [ ] User guide/UX docs cập nhật.
- [ ] QA matrix 12 kịch bản pass.
- [ ] Không còn `url: null` cố ý cho nguồn dán khi có nguồn tham chiếu.
