# QuickAssist Backend API Reference

Design material for an automated evaluation of the QuickAssist backend.

This document describes the **complete HTTP surface** of the backend (`apps/api`) as consumed by
the Chrome extension (`apps/extension`). For every endpoint it records:

- **Input** — method, path, authentication, headers, query parameters, body fields and their
  constraints (types, ranges, enums, defaults), taken from the generated OpenAPI schema.
- **Process** — what the server does with the request (validation, storage, quota, asynchronous
  work) and, where relevant, what the extension does around the call (pre-checks, caching,
  retries, aborts).
- **Output** — success status, response schema, field semantics, and the SSE event protocol for
  streaming endpoints.
- **Errors** — business error codes, the HTTP status each maps to, and the conditions that
  trigger them.

The document is written to be turned into executable checks: every constraint below is
observable from the wire (status code, headers, JSON shape, field enums, SSE ordering).

| Item | Value |
|---|---|
| Document date | 2026-11-19 |
| Backend entry point | `apps/api/src/quickassist/main.py` |
| Authoritative schema | `docs/api/openapi.json` (exported from the app, checked by CI) |
| Live schema in a running server | `GET /api/v1/openapi.json`, Swagger UI at `/docs` |
| API conventions (normative) | `docs/api/conventions.md` |
| Extension API layer | `apps/extension/src/shared/api/` (`http.ts`, `endpoints.ts`, `sse.ts`, `types.ts`) |
| Evaluation pipeline that already uses this surface over HTTP | `steady_evaluation/steady_backend.py` |

> **Keep the schema in sync.** The OpenAPI file is regenerated with
> `cd apps/api && python scripts/export_openapi.py`; CI runs the same command with `--check`.
> If an endpoint changes, this document must change with it.

---

## Table of contents

1. [Global conventions](#1-global-conventions)
2. [Endpoint index](#2-endpoint-index)
3. [Health](#3-health)
4. [Authentication](#4-authentication)
5. [Account and quota](#5-account-and-quota)
6. [AI settings (BYOK)](#6-ai-settings-byok)
7. [Folders](#7-folders)
8. [Notes](#8-notes)
9. [Search](#9-search)
10. [AI summaries](#10-ai-summaries)
11. [Page match (AutoChunk)](#11-page-match-autochunk)
12. [Chat (RAG, SSE)](#12-chat-rag-sse)
13. [Asynchronous note indexing](#13-asynchronous-note-indexing)
14. [Client behaviours worth emulating](#14-client-behaviours-worth-emulating)
15. [Environment knobs for evaluation](#15-environment-knobs-for-evaluation)
16. [Enum and limit reference](#16-enum-and-limit-reference)

---

## 1. Global conventions

### 1.1 Base URL and versioning

- All routes are mounted under **`/api/v1`**. Default local base URL:
  `http://localhost:8000/api/v1` (the extension's `VITE_API_BASE_URL`, default
  `http://localhost:8000/api/v1`).
- Breaking contract changes go to `/api/v2`; v1 is never changed silently.
- The trailing slash is not significant; the extension strips a trailing `/` from its base URL
  before appending paths.

### 1.2 Authentication and identity

- Protected endpoints require `Authorization: Bearer <access_token>`.
- **The user id is never sent in the body or query.** It is derived from the access token on the
  server. A resource that belongs to another user returns **404**, not 403, so its existence is
  not disclosed (IDOR protection).
- Access tokens are short-lived; `expires_in` (seconds) is returned by every token-issuing
  endpoint. The extension refreshes when `expiresAt - 30 s <= now`, and also on a `401`
  `TOKEN_EXPIRED` response (single retry of the original request).
- Endpoints that do **not** require a token: `GET /health/live`, `GET /health/ready`,
  `GET /auth/config`, `POST /auth/google/exchange`, `POST /auth/refresh`, `POST /auth/logout`,
  `POST /auth/dev-login`.

### 1.3 Request and response format

- JSON only. Field names are **`snake_case`**.
- Timestamps are ISO-8601 UTC strings (e.g. `2026-11-19T08:31:02.145000Z`). All ids are UUIDs.
- Requests with a body send `Content-Type: application/json`; the client accepts
  `Accept: application/json` (or `Accept: text/event-stream` for SSE endpoints).
- Successful create operations return `201`, destructive operations `204`, asynchronous
  re-indexing `202`, everything else `200`.

### 1.4 Error envelope

Every non-2xx response produced by the application uses one envelope:

```json
{
  "error": {
    "code": "NOTE_VERSION_CONFLICT",
    "message": "Ghi chú đã được sửa ở nơi khác",
    "details": { "current_version": 3 },
    "request_id": "9f0c2f0f6d7a4c2e"
  }
}
```

- `code` is stable and is the only field a client should branch on.
- `details` is free-form; documented uses: `current_version` on version conflicts, `errors`
  (`[{loc, msg}]`) on schema validation failures, `retry_after` (seconds) on rate limiting.
- Schema validation failures (FastAPI `RequestValidationError`) are normalised to
  `422 VALIDATION_ERROR`; the original input values are **not** echoed back.
- Unhandled exceptions become `500 INTERNAL_ERROR` with no stack trace.
- Business error classes map to HTTP status as follows:

| Business error class | HTTP | Default `code` |
|---|---|---|
| `AppError` (base) | 400 | `BAD_REQUEST` (overridden per call site) |
| `Unauthorized` | 401 | `UNAUTHORIZED` |
| `QuotaExceeded` | 402 | `QUOTA_EXCEEDED` |
| `Forbidden` | 403 | `FORBIDDEN` |
| `NotFound` | 404 | `NOT_FOUND` |
| `Conflict` | 409 | `CONFLICT` |
| `PayloadTooLarge` | 413 | `PAYLOAD_TOO_LARGE` |
| `Unprocessable` | 422 | `UNPROCESSABLE` |
| `RateLimited` | 429 | `RATE_LIMITED` (adds `Retry-After`) |
| `UpstreamError` | 502 | `UPSTREAM_ERROR` |
| any other exception | 500 | `INTERNAL_ERROR` |

Endpoint-specific codes replace the defaults (for example `NOTE_NOT_FOUND`, `FOLDER_EXISTS`,
`QUOTA_EXCEEDED`, `RATE_LIMITED`, `AI_UNAVAILABLE`).

### 1.5 Rate limiting

- Per **user**, per **bucket**, 60-second rolling window.
- Exceeding a limit returns **`429 RATE_LIMITED`** with a `Retry-After` header and
  `details.retry_after` (seconds).
- Buckets and default limits (all overridable by environment variable):

| Bucket | Applies to | Default / minute | Env var |
|---|---|---|---|
| `search` | `POST /search` | 30 | `RATE_LIMIT_SEARCH_PER_MINUTE` |
| `ai` | `POST /ai/chat`, `POST /ai/summaries` | 10 | `RATE_LIMIT_AI_PER_MINUTE` |
| `write` | note create/update/move/reindex/bulk-delete | 120 | `RATE_LIMIT_WRITE_PER_MINUTE` |
| `page_match` | `POST /ai/page-match`, `POST /ai/page-match/stream` | 6 | `RATE_LIMIT_PAGE_MATCH_PER_MINUTE` |
| `ai_settings_test` | `POST /me/ai-settings/test` | 6 | `RATE_LIMIT_AI_SETTINGS_TEST_PER_MINUTE` |

A quota exhaustion is a different condition and returns **402**, never 429 (see 1.6).

### 1.6 AI quota

- Each user has a token account. Default limit: **1,000,000 tokens** (`QUOTA_DEFAULT_TOKENS`).
- AI work (retrieval embedding, summaries, page match, chat generation) reserves tokens before
  calling the provider, then **commits the actual usage**; on failure or client abort the
  reservation is **released**, so failed calls are not charged.
- The ledger is keyed by `(user, request_id)`, so replaying the same logical request does not
  charge twice.
- Insufficient remaining tokens → **`402 QUOTA_EXCEEDED`** (client must not auto-retry; it is
  not a transient condition).
- `QuotaOut.billing_mode` is `server` when the server pays for AI, `byok` when the user's own key
  is used (see section 6).
- `QuotaOut.limit_enforced=false` in dev (`DEV_UNLIMITED=true`): usage is still recorded, but the
  server does not return `402` and rate limiting is off. Prod refuses to start with this flag.

### 1.7 Pagination

- Cursor pagination: `?limit=&cursor=` → `{ "items": [...], "next_cursor": "..." | null }`.
- `next_cursor` is `null` on the last page; an empty string or `null` means "start from the
  beginning" (`GET /notes`).
- Implementation detail visible to clients: the cursor is
  `base64url("<updated_at ISO-8601>|<note id>")` and pages are ordered by ascending
  `(updated_at, id)`. Treat it as opaque; only compare timestamps, never cursor strings.
- `GET /notes` accepts `limit` in `1..200`, default `50`.

### 1.8 Idempotency

- Header `Idempotency-Key` (string, ≤ 100 characters), accepted by `POST /notes` and
  `POST /ai/summaries`.
- Keys are retained for **24 hours**.
- Replaying a request with the same key and the same request hash returns the original result
  instead of creating a second resource (`POST /notes` still answers `201`).
- Reusing a key with a different payload → **`409 IDEMPOTENCY_KEY_REUSED`**.
- The extension **always** sends the header on `POST /notes`, using the UUID of the outbox item
  (see section 14).
- `POST /notes` without the header is accepted (manual/Swagger use) but provides no duplicate
  protection.

### 1.9 Request ID

- Every response carries `X-Request-ID` (generated by `RequestIdMiddleware`).
- The same value is included in error bodies as `error.request_id`.
- The extension records it on `AppError` for support/debugging.

### 1.10 Client-side timeouts (extension behaviour)

| Call | Timeout |
|---|---|
| All ordinary JSON requests | 15 s (`requestTimeoutMs`) |
| `POST /ai/summaries` | 120 s (`summaryRequestTimeoutMs`) |
| `POST /ai/page-match` (JSON) | 45 s (`pageMatchRequestTimeoutMs`) |
| SSE endpoints | no total timeout; cancelled by `AbortSignal` (user "Stop"/cancel) |

When a timeout fires, the client raises `NETWORK_ERROR` (status `0`); when the caller cancels,
it raises `ABORTED`.

---

## 2. Endpoint index

| Method | Path | Auth | Rate bucket | Purpose |
|---|---|---|---|---|
| GET | `/health/live` | public | — | liveness probe |
| GET | `/health/ready` | public | — | readiness (checks DB) |
| GET | `/auth/config` | public | — | expose server auth mode to clients |
| POST | `/auth/google/exchange` | public | — | exchange Google authorization code for app tokens |
| POST | `/auth/refresh` | public | — | rotate refresh token |
| POST | `/auth/logout` | public | — | revoke a refresh token |
| POST | `/auth/dev-login` | public | — | dev/test-only login (not in OpenAPI) |
| GET | `/me` | bearer | — | current profile |
| DELETE | `/me` | bearer | — | delete account and all data |
| GET | `/me/quota` | bearer | — | quota status |
| POST | `/me/quota/reset` | bearer | — | reset usage counters (dev/BYOK only) |
| GET | `/me/ai-settings` | bearer | — | read per-user AI provider settings |
| PUT | `/me/ai-settings` | bearer | — | write per-user AI provider settings |
| DELETE | `/me/ai-settings` | bearer | — | revert to server AI settings |
| POST | `/me/ai-settings/test` | bearer | `ai_settings_test` | test embedding + chat connectivity |
| GET | `/folders` | bearer | — | list folders |
| POST | `/folders` | bearer | — | create folder |
| PATCH | `/folders/{folder_id}` | bearer | — | rename folder |
| DELETE | `/folders/{folder_id}` | bearer | — | delete folder (notes move to Inbox) |
| POST | `/notes` | bearer | `write` | create note (idempotent) |
| GET | `/notes` | bearer | — | list / incremental sync |
| GET | `/notes/{note_id}` | bearer | — | read note |
| PATCH | `/notes/{note_id}` | bearer | `write` | update note (optimistic lock) |
| DELETE | `/notes/{note_id}` | bearer | — | soft-delete note |
| POST | `/notes/bulk-delete` | bearer | `write` | delete many notes |
| POST | `/notes/move` | bearer | `write` | move many notes to a folder |
| POST | `/notes/{note_id}/reindex` | bearer | `write` | retry semantic indexing |
| PUT | `/notes/{note_id}/summary` | bearer | — | save a user-confirmed summary |
| POST | `/search` | bearer | `search` | semantic search grouped by source |
| POST | `/ai/summaries` | bearer | `ai` | generate a summary preview |
| POST | `/ai/page-match` | bearer | `page_match` | find matching passages on a page (JSON) |
| POST | `/ai/page-match/stream` | bearer | `page_match` | same, streaming progress over SSE |
| POST | `/ai/chat` | bearer | `ai` | RAG chat over the note library (SSE) |

---

## 3. Health

### 3.1 `GET /api/v1/health/live`

**Input** — none. No authentication.

**Process** — returns a constant payload; does not touch the database.

**Output** — `200`

```json
{ "status": "ok" }
```

**Errors** — none expected.

### 3.2 `GET /api/v1/health/ready`

**Input** — none. No authentication.

**Process** — opens a database session and pings the database (`SystemRepository.ping`). Used by
orchestrators to decide whether the service can serve traffic.

**Output** — `200`

```json
{ "status": "ok", "db": "ok" }
```

**Errors** — if the database is unreachable the exception is unhandled and becomes
`500 INTERNAL_ERROR`.

---

## 4. Authentication

Google login is an **Authorization Code + PKCE** flow executed by the extension's background
service worker via `chrome.identity.launchWebAuthFlow`. The extension holds only the public
`client_id`; the server holds the client secret and performs the token exchange.

### 4.1 `GET /api/v1/auth/config`

**Input** — none. No authentication.

**Process** — returns the server's authentication mode. The extension reads this to decide
whether to auto-login (self-host `local` mode) or show the Google button.

**Output** — `200`

```json
{ "auth_mode": "google" }
```

| Field | Type | Values |
|---|---|---|
| `auth_mode` | string | `google`, `local` |

The response deliberately contains no email: in `local` mode the server chooses the account.

**Errors** — none.

### 4.2 `POST /api/v1/auth/google/exchange`

**Input**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `code` | string | yes | 1..2048 chars |
| `code_verifier` | string | yes | 43..128 chars (PKCE, S256) |
| `redirect_uri` | string | yes | ≤ 512 chars; must be the extension redirect (`https://<extension-id>.chromiumapp.org/`) and be allow-listed (`OAUTH_ALLOWED_REDIRECT_URIS`) |
| `nonce` | string | yes | 16..128 chars |

`state` is **not** sent to the server; the extension verifies it locally after the redirect. The
server validates the `nonce` inside the Google ID token.

**Process**

1. Calls Google's token endpoint with the authorization code and verifier, using the server's
   client secret.
2. Validates the returned ID token (issuer, audience, expiry, `nonce`).
3. Upserts the user by Google subject (`sub`), storing email, display name and picture.
4. Issues an access/refresh token pair and records the session with the request's `User-Agent`.

**Output** — `200 TokenPairOut`

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "rt_0f2c...",
  "expires_in": 900,
  "token_type": "Bearer",
  "is_new_user": false
}
```

| Field | Type | Notes |
|---|---|---|
| `access_token` | string | bearer token for subsequent requests |
| `refresh_token` | string | long-lived, rotated on every refresh |
| `expires_in` | integer | access-token lifetime in seconds |
| `token_type` | string | always `Bearer` (default) |
| `is_new_user` | boolean | `true` if the account was created by this exchange (default `false`) |

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 401 | OIDC client code, e.g. `OAUTH_NONCE_MISMATCH` | invalid or expired authorization code, nonce mismatch, ID-token verification failure |
| 422 | `VALIDATION_ERROR` | schema violation (e.g. short verifier) |
| 502 | `OAUTH_UPSTREAM` | Google token/OIDC endpoint unreachable or returned an upstream error |

### 4.3 `POST /api/v1/auth/refresh`

**Input**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `refresh_token` | string | yes | 20..256 chars |

No access token is required — refresh must work after the access token expires.

**Process**

1. Looks up the session by refresh token.
2. Rejects unknown tokens, revoked sessions and expired sessions.
3. **Rotates** the pair: the presented refresh token is invalidated and a new pair is issued;
   presenting a rotated token again is treated as reuse (family compromise).

**Output** — `200 TokenPairOut` (same shape as 4.2).

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 401 | `REFRESH_INVALID` | token not found / malformed |
| 401 | `REFRESH_REUSED` | a rotated (already used) token was presented |
| 401 | `REFRESH_EXPIRED` | session expired |
| 422 | `VALIDATION_ERROR` | length constraints violated |

### 4.4 `POST /api/v1/auth/logout`

**Input**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `refresh_token` | string | yes | 20..256 chars |

No access token is required.

**Process** — revokes the session identified by the refresh token. The extension clears its local
tokens regardless of the server outcome (the call is best-effort).

**Output** — `204` with no body.

**Errors** — `422 VALIDATION_ERROR` on schema violation. An unknown token is not an error.

### 4.5 `POST /api/v1/auth/dev-login`

> **Not part of the public OpenAPI document** (`include_in_schema=False`). It is used by the
> self-host `local` mode and by E2E builds. Evaluation pipelines use it as the credential source.

**Input**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `email` | string | no | ≤ 320 chars; default `dev@quickassist.local` |

**Process**

1. Rejected unless `APP_ENV` is `dev` or `test` **and** `ENABLE_DEV_LOGIN=true`
   (`403 DEV_LOGIN_DISABLED` otherwise).
2. If `AUTH_MODE=local`, the client-supplied email is **ignored** and `LOCAL_AUTH_EMAIL` is used,
   so a self-hosted single-user server always logs into the same account.
3. Upserts the user with `sub = "dev:<email>"` (the same email always maps to the same user),
   name `Dev User`, no picture.
4. Issues a token pair exactly like a normal login.

**Output** — `200 TokenPairOut` (same shape as 4.2).

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 403 | `DEV_LOGIN_DISABLED` | dev login not enabled / wrong environment |
| 422 | `VALIDATION_ERROR` | email longer than 320 chars |

> **Evaluation note:** dev-login never creates a fresh account per run, so isolate test data by
> creating a folder per run and scoping `search`/`chat` with `folder_id` (this is what
> `steady_evaluation` does).

---

## 5. Account and quota

### 5.1 `GET /api/v1/me`

**Input** — bearer token only.

**Process** — loads the profile of the authenticated user.

**Output** — `200 UserOut`

```json
{
  "id": "3d1c9a52-8f9e-4a67-b5c2-1e6d9f0a7b11",
  "email": "user@example.com",
  "display_name": "Nguyen Van A",
  "avatar_url": "https://lh3.googleusercontent.com/...",
  "created_at": "2026-10-02T04:12:33.512000Z"
}
```

| Field | Type | Nullable |
|---|---|---|
| `id` | uuid | no |
| `email` | string | no |
| `display_name` | string | yes |
| `avatar_url` | string | yes |
| `created_at` | date-time | no |

**Errors** — `401 TOKEN_MISSING` / `TOKEN_EXPIRED` / `TOKEN_INVALID`.

### 5.2 `DELETE /api/v1/me`

**Input** — bearer token only.

**Process** — deletes the account and **all** related data (notes, chunks, folders, quota ledger,
sessions, AI settings). Irreversible.

**Output** — `204` with no body.

**Errors** — `401` as above.

### 5.3 `GET /api/v1/me/quota`

**Input** — bearer token only.

**Process** — ensures a quota account exists (creating it with the default limit if needed) and
returns the counters.

**Output** — `200 QuotaOut`

```json
{
  "limit_tokens": 1000000,
  "used_tokens": 14320,
  "reserved_tokens": 0,
  "remaining_tokens": 985680,
  "billing_mode": "server",
  "limit_enforced": true
}
```

| Field | Type | Meaning |
|---|---|---|
| `limit_tokens` | integer | total allowance |
| `used_tokens` | integer | committed usage |
| `reserved_tokens` | integer | in-flight reservations |
| `remaining_tokens` | integer | `max(0, limit - used - reserved)` |
| `billing_mode` | string | `server` or `byok` |
| `limit_enforced` | boolean | `false` = dev unlimited (still records usage, never blocks) |

**Errors** — `401` as above.

### 5.4 `POST /api/v1/me/quota/reset`

**Input** — bearer token only.

**Process** — resets `used_tokens`/`reserved_tokens` to zero (keeps the limit). Allowed only in a
dev-login environment (`APP_ENV=dev|test` with dev login enabled) **or** for a BYOK user, who
pays for AI with their own key.

**Output** — `200 QuotaOut` (post-reset counters).

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 403 | `RESET_NOT_ALLOWED` | production user using server-paid AI |
| 401 | token errors | missing/invalid token |

---

## 6. AI settings (BYOK)

Per-user AI provider configuration (ADR-0016). The server encrypts the API key with AES-GCM
before storing it and **never returns it**: responses expose only `has_key` and `key_hint`.
All AI calls are proxied by the server; the key never reaches the extension.

### 6.1 `GET /api/v1/me/ai-settings`

**Input** — bearer token only.

**Process** — returns the user's configuration plus the server defaults, so the UI can show what
`inherit` would use.

**Output** — `200 AISettingsOut`

```json
{
  "mode": "byok",
  "provider": "openai",
  "base_url": "http://127.0.0.1:8080/v1",
  "chat_model": "chat",
  "embedding_model": "embed",
  "has_key": true,
  "key_hint": "…c3f9",
  "timeout_seconds": 60.0,
  "server_default": {
    "provider": "openai",
    "chat_model": "gpt-4o-mini",
    "embedding_model": "text-embedding-3-small"
  },
  "rebuild": null,
  "rebuild_note_count": 0
}
```

| Field | Type | Notes |
|---|---|---|
| `mode` | string | `inherit` (use server config) or `byok` |
| `provider` | string \| null | `openai` or `gemini` (OpenAI-compatible local servers use `openai` + `base_url`) |
| `base_url` | string \| null | provider base URL |
| `chat_model` / `embedding_model` | string \| null | model names |
| `has_key` | boolean | whether a key is stored |
| `key_hint` | string \| null | masked tail of the key; never the key |
| `timeout_seconds` | number \| null | per-call timeout |
| `server_default.provider` | string | `openai`, `gemini` or `mock` |
| `server_default.chat_model` / `embedding_model` | string | server-wide models |
| `rebuild` | object \| null | `{ "required": bool, "notes": int }` when an embedding change triggered a rebuild |
| `rebuild_note_count` | integer | convenience count (default `0`) |

**Errors** — `401` token errors.

### 6.2 `PUT /api/v1/me/ai-settings`

**Input** — `AISettingsIn`

| Field | Type | Required | Constraints |
|---|---|---|---|
| `mode` | string | **yes** | `inherit`, `byok` |
| `provider` | string \| null | no | `openai`, `gemini` |
| `base_url` | string \| null | no | ≤ 512 chars; must match an allow-listed prefix when `AI_BASE_URL_ALLOWLIST` is set (CSV of `scheme://host:port/path` prefixes; empty = any `http(s)`) |
| `api_key` | string \| null | no | ≤ 4096 chars. `null` = keep the stored key, `""` = delete the key (local models), non-empty = replace |
| `chat_model` | string \| null | no | ≤ 100 chars |
| `embedding_model` | string \| null | no | ≤ 100 chars |
| `embedding_dim` | integer \| null | no | 1..100000; advisory native dimension measured by the client (used to reject > 1536 early) |
| `timeout_seconds` | number \| null | no | 5..600 |

**Process**

1. Validates mode/provider/base URL/key format.
2. Encrypts and stores the key when a non-empty value is supplied; `null` keeps the previous key;
   `""` removes it.
3. Computes an embedding fingerprint from provider/base URL/model/dimension. If it changed, the
   whole index is rebuilt: notes are set to `PROCESSING` and re-index jobs are enqueued; the
   response carries `rebuild`.
4. Dimensions above the canonical 1536 are rejected (final guard also applies at embedding time;
   vectors shorter than 1536 are zero-padded — e.g. 768-dimensional models are padded).

**Output** — `200 AISettingsOut` (same shape as 6.1, including `rebuild` when applicable).

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 400 | `AI_CONFIG_INVALID` | invalid configuration (mode/provider/base URL/key) |
| 422 | `VALIDATION_ERROR` | schema violation (ranges, lengths) |
| 401 | token errors | missing/invalid token |

### 6.3 `DELETE /api/v1/me/ai-settings`

**Input** — bearer token only.

**Process** — reverts to `mode=inherit` (server configuration), deletes the stored key, and
rebuilds the index if the effective embedding fingerprint changes.

**Output** — `200 AISettingsOut` (`mode` becomes `inherit`; `has_key` false; `rebuild` possibly set).

**Errors** — `401` token errors.

### 6.4 `POST /api/v1/me/ai-settings/test`

**Input** — `AISTestIn` (like `AISettingsIn` without `mode`)

| Field | Type | Required | Constraints |
|---|---|---|---|
| `provider` | string \| null | no | `openai`, `gemini` |
| `base_url` | string \| null | no | ≤ 512 chars |
| `api_key` | string \| null | no | ≤ 4096 chars; missing → the stored key is used |
| `chat_model` | string \| null | no | ≤ 100 chars |
| `embedding_model` | string \| null | no | ≤ 100 chars |
| `timeout_seconds` | number \| null | no | 5..600 |

**Process** — sends one tiny embedding request and one tiny chat completion to the configured
provider, sequentially. Fixed **30 s** timeout, no retry. This is a connectivity check only; it
does not save anything.

**Output** — `200 AISTestOut`

```json
{
  "ok": true,
  "code": null,
  "message": null,
  "stage": null,
  "embedding_dim": 1536,
  "embedding": { "model": "embed", "dim": 1536, "latency_ms": 41, "padded": false },
  "chat": { "model": "chat", "latency_ms": 812, "sample": "Hà Nội" }
}
```

| Field | Type | Notes |
|---|---|---|
| `ok` | boolean | overall success (required) |
| `code` | string \| null | failure code when `ok=false` |
| `message` | string \| null | human-readable failure reason |
| `stage` | string \| null | which step failed: `embedding`, `chat` |
| `embedding_dim` | integer \| null | measured native dimension |
| `embedding` | object \| null | `{ model, dim, latency_ms, padded }` |
| `chat` | object \| null | `{ model, latency_ms, sample }` |

**Errors** — `429 RATE_LIMITED` (bucket `ai_settings_test`, `Retry-After`), `422 VALIDATION_ERROR`,
`401` token errors. Provider failures are reported **inside** a `200` body with `ok=false`.

---

## 7. Folders

The **Inbox** is a default folder created automatically; it cannot be renamed or deleted. Notes
without a folder belong to it (`folder_id` is never null on a stored note).

### 7.1 `GET /api/v1/folders`

**Input** — bearer token only.

**Process** — returns the user's folders, including Inbox.

**Output** — `200 FolderOut[]`

```json
[
  {
    "id": "6b1f0d7e-2c4a-4f18-9c3e-7a2b5d8e1f04",
    "name": "Inbox",
    "is_default": true,
    "created_at": "2026-10-02T04:12:33.512000Z",
    "updated_at": "2026-10-02T04:12:33.512000Z"
  }
]
```

**Errors** — `401` token errors.

### 7.2 `POST /api/v1/folders`

**Input**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `name` | string | yes | 1..100 chars |

**Process** — creates a folder for the user. Names are unique per user (case-sensitive as stored
by the database).

**Output** — `201 FolderOut`.

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 409 | `FOLDER_EXISTS` | a folder with that name already exists |
| 422 | `VALIDATION_ERROR` | empty or > 100 chars |
| 401 | token errors | |

### 7.3 `PATCH /api/v1/folders/{folder_id}`

**Input**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `folder_id` | uuid | yes | path |
| `name` | string | yes | 1..100 chars |

**Process** — renames the folder; refuses to touch the default folder.

**Output** — `200 FolderOut`.

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 404 | `FOLDER_NOT_FOUND` | unknown id or another user's folder |
| 409 | `FOLDER_IS_DEFAULT` | target is Inbox |
| 409 | `FOLDER_EXISTS` | name collision |
| 422 | `VALIDATION_ERROR` | invalid body |

### 7.4 `DELETE /api/v1/folders/{folder_id}`

**Input** — `folder_id` (uuid, path).

**Process** — deletes the folder and moves **all** its notes to Inbox in the same transaction
(no note is lost). The extension then re-syncs notes, because their `folder_id`/`updated_at`
changed.

**Output** — `204` with no body.

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 404 | `FOLDER_NOT_FOUND` | unknown id / other user |
| 409 | `FOLDER_IS_DEFAULT` | target is Inbox |

---

## 8. Notes

A note is a captured text excerpt with optional title and source URL. Its `index_status` tracks
asynchronous semantic indexing (section 13).

### 8.1 `POST /api/v1/notes`

**Input** — `NoteCreateIn`

| Field | Type | Required | Constraints |
|---|---|---|---|
| `content` | string | **yes** | ≥ 1 char; cleaned (NUL removed, trimmed); > 20,000 chars → `413 NOTE_TOO_LONG` |
| `title` | string \| null | no | ≤ 500 chars |
| `url` | string (uri) \| null | no | 1..2083 chars, must be a valid URI. The server derives `domain` from it |
| `folder_id` | uuid \| null | no | `null`/omitted → Inbox; unknown id → `404 FOLDER_NOT_FOUND` |

Header: `Idempotency-Key` (≤ 100 chars). The extension always sends a UUID.

**Process**

1. Resolve the folder (Inbox when `folder_id` is absent).
2. Clean content: remove NUL bytes, trim; enforce `MAX_NOTE_CHARS` (default 20,000).
3. Idempotency guard: a replayed key with the same request hash returns the existing note; a
   reused key with a different payload → `409 IDEMPOTENCY_KEY_REUSED`.
4. Insert the note with `index_status = "PROCESSING"`, `version = 1`, and enqueue the
   `semantic_search.index_note` job **in the same transaction**.
5. Commit and return the note. Indexing happens asynchronously in the worker.

The extension slices the selection to 20,000 chars and warns the user before sending; it also
stores the note in a local outbox first (section 14).

**Output** — `201 NoteOut`

```json
{
  "id": "b8a4c0d2-6e1f-4a9b-8c7d-2f3e5a6b7c88",
  "folder_id": "6b1f0d7e-2c4a-4f18-9c3e-7a2b5d8e1f04",
  "url": "https://example.com/article",
  "domain": "example.com",
  "title": "Example article",
  "content": "The selected text…",
  "summary_text": null,
  "index_status": "PROCESSING",
  "version": 1,
  "created_at": "2026-11-19T08:31:02.145000Z",
  "updated_at": "2026-11-19T08:31:02.145000Z",
  "deleted_at": null
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | note id |
| `folder_id` | uuid | never null |
| `url` | string \| null | source URL |
| `domain` | string \| null | derived from `url` by the server |
| `title` | string \| null | source title |
| `content` | string | full excerpt |
| `summary_text` | string \| null | saved summary (section 8.9) |
| `index_status` | string | `PROCESSING`, `READY`, `SKIPPED`, `FAILED` |
| `version` | integer | optimistic-lock counter, starts at 1 |
| `created_at` / `updated_at` | date-time | server timestamps |
| `deleted_at` | date-time \| null | tombstone marker |

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 404 | `FOLDER_NOT_FOUND` | `folder_id` unknown or not owned |
| 409 | `IDEMPOTENCY_KEY_REUSED` | same key, different payload |
| 413 | `NOTE_TOO_LONG` | content above `MAX_NOTE_CHARS` |
| 422 | `VALIDATION_ERROR` | schema violation (empty content, title/url limits) |
| 429 | `RATE_LIMITED` | `write` bucket |
| 401 | token errors | |

### 8.2 `GET /api/v1/notes`

**Input** — query parameters

| Parameter | Type | Required | Constraints / meaning |
|---|---|---|---|
| `folder_id` | uuid | no | filter by folder |
| `updated_since` | date-time | no | incremental sync; when present the response also contains tombstones (`deleted_at` set) |
| `cursor` | string | no | opaque cursor from `next_cursor` |
| `limit` | integer | no | 1..200, default 50 |

**Process**

1. Reads the page ordered by ascending `(updated_at, id)`, fetching `limit + 1` rows to detect
   whether another page exists.
2. When `updated_since` is present, deleted notes are included as tombstones.
3. Encodes the next cursor from the last returned row.

**Output** — `200`

```json
{
  "items": [ { "…": "NoteOut" } ],
  "next_cursor": "MjAyNi0xMS0xOVQwODozMTowMi4xNDUwMDBafGI4YTRjMGQyLTZlMWYtNGE5Yi04YzdkLTJmM2U1YTZiN2M4OA=="
}
```

`next_cursor` is `null` on the last page. It is base64url of `<updated_at>|<id>`; treat as opaque.

**Errors** — `422 VALIDATION_ERROR` (bad uuid/limit), `401` token errors.

### 8.3 `GET /api/v1/notes/{note_id}`

**Input** — `note_id` (uuid, path).

**Process** — loads a non-deleted note owned by the caller.

**Output** — `200 NoteOut`.

**Errors** — `404 NOTE_NOT_FOUND` (unknown, another user's, or deleted), `422 VALIDATION_ERROR`
(malformed uuid), `401` token errors.

### 8.4 `PATCH /api/v1/notes/{note_id}`

**Input** — `NoteUpdateIn`

| Field | Type | Required | Constraints |
|---|---|---|---|
| `version` | integer | **yes** | ≥ 1; the version the client currently holds |
| `content` | string \| null | no | ≥ 1 char after cleaning; > 20,000 → `413 NOTE_TOO_LONG`; `null` = do not change |
| `title` | string \| null | no | ≤ 500 chars; empty/whitespace becomes `null`; `null` = do not change |
| `folder_id` | uuid \| null | no | unknown id → `404 FOLDER_NOT_FOUND`; `null` means "do not change" |

**Process**

1. Locks the row for update; missing/deleted → `404 NOTE_NOT_FOUND`.
2. Compares `version` with the stored one → mismatch is `409 NOTE_VERSION_CONFLICT` with
   `details.current_version`.
3. If `content` changed: clean it, set `index_status = PROCESSING`, bump `index_rev`, and
   enqueue re-indexing.
4. If `folder_id` changed: resolve it, update the note, and enqueue re-indexing (the chunk table
   stores `folder_id` used for folder-scoped retrieval).
5. Increment `version` and commit.

**Output** — `200 NoteOut` (new `version`, possibly `PROCESSING`).

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 404 | `NOTE_NOT_FOUND` | unknown / deleted / other user |
| 404 | `FOLDER_NOT_FOUND` | target folder unknown |
| 409 | `NOTE_VERSION_CONFLICT` | stale `version` (`details.current_version`) |
| 413 | `NOTE_TOO_LONG` | new content too long |
| 422 | `VALIDATION_ERROR` | schema violation |
| 429 | `RATE_LIMITED` | `write` bucket |

### 8.5 `DELETE /api/v1/notes/{note_id}`

**Input** — `note_id` (uuid, path).

**Process** — **soft-deletes** the note (`deleted_at` set), publishes a change event so the worker
removes its chunks from the index, and commits. The note disappears from normal `GET`/`list`;
incremental sync (`updated_since`) exposes it as a tombstone so other clients can delete their
local copy.

**Output** — `204` with no body.

**Errors** — `404 NOTE_NOT_FOUND`, `422 VALIDATION_ERROR`, `401` token errors.

### 8.6 `POST /api/v1/notes/bulk-delete`

**Input** — `BulkDeleteIn`

| Field | Type | Required | Constraints |
|---|---|---|---|
| `ids` | uuid[] | yes | 1..200 items |

**Process** — soft-deletes every owned, non-deleted note in the list and publishes one change
event per note. Ids that are unknown, already deleted or owned by another user are silently
ignored (they simply do not contribute to the count).

**Output** — `200`

```json
{ "deleted": 3 }
```

**Errors** — `422 VALIDATION_ERROR` (empty list / > 200 / bad uuid), `429 RATE_LIMITED`,
`401` token errors.

### 8.7 `POST /api/v1/notes/move`

**Input** — `NotesMoveIn`

| Field | Type | Required | Constraints |
|---|---|---|---|
| `ids` | uuid[] | yes | 1..200 items |
| `folder_id` | uuid \| null | no | destination; `null` → Inbox |

**Process**

1. Resolve the destination folder (Inbox when `folder_id` is null/absent; `404 FOLDER_NOT_FOUND`
   if unknown).
2. Deduplicate ids; move only notes owned by the caller that are not deleted.
3. For every moved note, enqueue an index job that updates `NoteChunk.folder_id` **in the same
   transaction**.
4. Return the number moved plus the ids that could not be moved.

**Output** — `200`

```json
{ "moved": 2, "missing": ["f1c2…"] }
```

**Errors** — `404 FOLDER_NOT_FOUND`, `422 VALIDATION_ERROR`, `429 RATE_LIMITED`, `401` token errors.

### 8.8 `POST /api/v1/notes/{note_id}/reindex`

**Input** — `note_id` (uuid, path).

**Process** — the user-facing "Retry" action for a note whose indexing ended in `FAILED` or
`SKIPPED`. Resets `index_status` to `PROCESSING`, clears `index_error`, bumps `index_rev`, and
enqueues a new index job.

**Output** — **`202`** `NoteOut` (with `index_status = "PROCESSING"`).

**Errors** — `404 NOTE_NOT_FOUND`, `422 VALIDATION_ERROR`, `429 RATE_LIMITED`, `401` token errors.

### 8.9 `PUT /api/v1/notes/{note_id}/summary`

**Input** — `NoteSummaryIn`

| Field | Type | Required | Constraints |
|---|---|---|---|
| `version` | integer | **yes** | ≥ 1; the version the client holds |
| `summary_text` | string | yes | 1..10,000 chars |

**Process** — saves a summary the user explicitly confirmed. Locks the row, checks `version`
(409 on mismatch), stores the trimmed summary and increments `version`. This is a plain write:
the summary comes from `POST /ai/summaries`, which does not persist anything.

**Output** — `200 NoteOut`.

**Errors** — `404 NOTE_NOT_FOUND`, `409 NOTE_VERSION_CONFLICT`, `422 VALIDATION_ERROR`,
`401` token errors.

---

## 9. Search

### 9.1 `POST /api/v1/search`

**Input** — `SearchIn`

| Field | Type | Required | Constraints |
|---|---|---|---|
| `query` | string | **yes** | 1..1000 chars |
| `folder_id` | uuid \| null | no | restrict retrieval to one folder |
| `max_sources` | integer | no | 1..20, default 5 — maximum number of **sources** (domains) returned |

**Process**

1. Open a quota lease (`search`) for the estimated query tokens.
2. Embed the query with the effective embedding provider.
3. Vector-search the note chunks (candidate depth derived from `max_sources` × notes per source,
   capped by `search_candidate_k`; default candidate cap 60).
4. Group results **by source**: domain (null domain is labelled "unknown source"), ranked by the
   hybrid score (vector similarity combined with full-text rank — RRF).
5. Apply thresholds: vector `similarity ≥ 0.5` and RRF `score ≥ 0.03` (both configurable).
6. Return at most `max_sources` sources, each with at most 10 notes
   (`SEARCH_NOTES_PER_SOURCE`), each note represented by its best chunk.
7. Commit actual token usage; release the reservation on failure.

The same retrieval routine backs chat (section 12), so both features apply identical grouping and
thresholds.

**Output** — `200 SearchOut`

```json
{
  "sources": [
    {
      "domain": "example.com",
      "label": "Example article",
      "source_rank": 1,
      "note_count": 2,
      "notes": [
        {
          "note_id": "b8a4c0d2-6e1f-4a9b-8c7d-2f3e5a6b7c88",
          "title": "Example article",
          "url": "https://example.com/article",
          "summary": null,
          "snippet": "…matched passage…",
          "score": 0.031,
          "similarity": 0.78
        }
      ]
    }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `sources[].domain` | string \| null | source domain; `null` = unknown source |
| `sources[].label` | string | display label (title/domain) |
| `sources[].source_rank` | integer | 1-based rank |
| `sources[].note_count` | integer | number of notes in this source |
| `sources[].notes[].note_id` | uuid | note id |
| `sources[].notes[].title` | string \| null | note title |
| `sources[].notes[].url` | string \| null | note URL |
| `sources[].notes[].summary` | string \| null | saved summary |
| `sources[].notes[].snippet` | string | matched text excerpt |
| `sources[].notes[].score` | number | hybrid score (RRF) |
| `sources[].notes[].similarity` | number | cosine similarity |

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 402 | `QUOTA_EXCEEDED` | not enough tokens for the query embedding |
| 422 | `VALIDATION_ERROR` | schema violation |
| 429 | `RATE_LIMITED` | `search` bucket (default 30/min) |
| 502 | `AI_UNAVAILABLE` | embedding provider failure (not declared in OpenAPI, produced by the global error handler) |
| 401 | token errors | |

> An empty note library is not an error: the response is `{ "sources": [] }`.

---

## 10. AI summaries

### 10.1 `POST /api/v1/ai/summaries`

**Input** — `SummaryIn`

| Field | Type | Required | Constraints |
|---|---|---|---|
| `text` | string \| null | one of `text` / `note_id` | ≥ 1 char; cleaned; > 30,000 chars → `413 SUMMARY_INPUT_TOO_LONG` |
| `note_id` | uuid \| null | one of `text` / `note_id` | exactly one of the two must be provided |

Header: optional `Idempotency-Key` (≤ 100 chars).

**Process**

1. Enforce "exactly one of `text` and `note_id`" → `400 SUMMARY_INPUT_INVALID` otherwise.
2. When `note_id` is given, load the note content (`404 NOTE_NOT_FOUND` if missing).
3. Strip NUL bytes and whitespace; empty text → `400 SUMMARY_INPUT_INVALID`;
   above `MAX_SUMMARY_INPUT_CHARS` (30,000) → `413 SUMMARY_INPUT_TOO_LONG`.
4. Build the summarisation prompt and estimate input + output tokens.
5. Open a quota lease keyed by `request_id` (derived from the idempotency key). A key that was
   already used → `409 IDEMPOTENCY_KEY_REUSED` (the AI is not called twice for free).
6. Call the chat model; commit actual usage; release the reservation on failure.
7. Return the preview. **Nothing is written to the database** — the user must confirm, after
   which the client calls `PUT /notes/{id}/summary`.

The extension sends either `{ note_id }` or `{ text: <selection trimmed to 30,000 chars> }` and
uses a 120-second timeout.

**Output** — `200 SummaryOut`

```json
{
  "summary": "Summary text…",
  "tokens_used": 214,
  "request_id": "summary:3d1c9a52-…:b0f1…"
}
```

| Field | Type | Notes |
|---|---|---|
| `summary` | string | generated summary text |
| `tokens_used` | integer | tokens charged for this call |
| `request_id` | string | internal request identifier for the ledger |

**Errors**

| HTTP | Code | Condition |
|---|---|---|
| 400 | `SUMMARY_INPUT_INVALID` | both or neither of `text`/`note_id`, or empty text |
| 404 | `NOTE_NOT_FOUND` | `note_id` unknown / not owned |
| 402 | `QUOTA_EXCEEDED` | not enough tokens |
| 409 | `IDEMPOTENCY_KEY_REUSED` | key already used with a different request |
| 413 | `SUMMARY_INPUT_TOO_LONG` | input above 30,000 chars |
| 422 | `VALIDATION_ERROR` | schema violation |
| 429 | `RATE_LIMITED` | `ai` bucket (default 10/min) |
| 502 | `AI_UNAVAILABLE` | provider failure |

---

## 11. Page match (AutoChunk)

Stateless "find these passages in this page" operation: it returns a **preview** and never writes
to the database. To keep a result, the client creates a normal note with `POST /notes`.

Two endpoints share one service:

- `POST /ai/page-match` — one JSON response.
- `POST /ai/page-match/stream` — SSE progress events, then the same result.

The extension always uses the streaming variant (progress UI, cancel button).

### 11.1 Shared input — `PageMatchIn`

| Field | Type | Required | Constraints |
|---|---|---|---|
| `query` | string | **yes** | 1..500 chars — the user's intent in natural language |
| `html` | string \| null | one of `html` / `text` | ≥ 1 char; page HTML with `script`/`style`/`noscript`/`template`/`svg` removed; encoded size ≤ 2,000,000 bytes (`PAGE_MATCH_MAX_HTML_BYTES`) |
| `text` | string \| null | one of `html` / `text` | ≥ 1 char; pasted content (PDF/Word/chat/e-mail) |
| `url` | string \| null | no | ≤ 2048 chars; log/metadata only |
| `title` | string \| null | no | ≤ 500 chars; log/metadata only |
| `scan_all` | boolean | no | default `false`; `true` removes the 50,000-character scan cap and embeds every block in batches |

Exactly one of `html` and `text` must be present; providing both or neither is a request error.

### 11.2 Shared process

1. **Synchronous validation** (before any streaming): query present/≤ 500, exactly one source,
   HTML size ≤ 2 MB, pasted text non-empty.
2. **Extraction**:
   - `html` → Trafilatura in a process pool, producing text blocks;
   - `text` → paragraph splitting with reflow and merging;
   - blocks are at most 1,200 characters; longer blocks are split at sentence boundaries.
3. **Scan cap**: unless `scan_all=true`, only the first 50,000 extracted characters are scanned;
   exceeding it sets `truncated = true` in the result.
4. **Embedding**: the query is embedded once, then blocks are embedded in batches of 32 blocks,
   each batch with its own timeout. All batches share **one quota lease**; usage is committed at
   the end and released if the client aborts or an error occurs.
5. **Candidate selection**: cosine similarity between the query vector and each block, filtered by
   a minimum similarity, then truncated to the top candidates.
6. **LLM verification**: candidates are sent to the chat model, which scores each on a 0..1
   confidence scale. This step uses a **second quota lease**.
7. **Degradation**: if verification fails (model error, timeout, unparsable JSON, quota exhausted
   at that step) the endpoint still succeeds: cosine candidates ≥ 0.5 are returned with
   `verified = false` and `warning = "VERIFY_UNAVAILABLE"`.
8. Only items with confidence ≥ 0.5 (`PAGE_MATCH_MIN_CONFIDENCE`) are returned, ordered by their
   position on the page. `match_ratio` = total matched characters ÷ total extracted characters.

### 11.3 `POST /api/v1/ai/page-match`

**Input** — `PageMatchIn` (above).

**Process** — runs the pipeline above and returns the final result once.

**Output** — `200 PageMatchOut`

```json
{
  "mode": "segments",
  "match_ratio": 0.12,
  "warning": null,
  "items": [
    {
      "id": "b07",
      "occ": 0,
      "text": "…matched block…",
      "score": 0.81,
      "confidence": 0.93,
      "verified": true
    }
  ],
  "total_chars": 18342,
  "truncated": false,
  "full_text": null
}
```

| Field | Type | Notes |
|---|---|---|
| `mode` | string | `segments` (matched passages) or `full_page` |
| `match_ratio` | number | matched characters ÷ extracted characters |
| `warning` | string \| null | `VERIFY_UNAVAILABLE` when verification was skipped/failed, else `null` |
| `items[].id` | string | block id within this scan (`b00`, `b01`, …) |
| `items[].occ` | integer | 0-based occurrence index of exactly this text on the page (for highlighting) |
| `items[].text` | string | block text |
| `items[].score` | number | cosine similarity between query and block |
| `items[].confidence` | number | final 0..1 confidence: LLM score when `verified`, cosine when not |
| `items[].verified` | boolean | whether the LLM evaluated this item |
| `total_chars` | integer | extracted main-content characters |
| `truncated` | boolean | `true` when the page exceeded the scan cap |
| `full_text` | string \| null | whole page text; only present when `mode = "full_page"` |

**Errors** (JSON envelope, standard status)

| HTTP | Code | Condition |
|---|---|---|
| 402 | `QUOTA_EXCEEDED` | not enough tokens to embed |
| 413 | `PAGE_TOO_LONG` | HTML above 2 MB |
| 422 | `PAGE_NO_CONTENT` | extraction found no main content (or empty pasted text) |
| 422 | `PAGE_MATCH_QUERY_INVALID` | invalid/empty query |
| 422 | `VALIDATION_ERROR` | schema violation |
| 429 | `RATE_LIMITED` | `page_match` bucket (default 6/min) |
| 502 | `AI_UNAVAILABLE` | embedding provider failure |

### 11.4 `POST /api/v1/ai/page-match/stream`

**Input** — identical `PageMatchIn`.

**Process** — validates synchronously (errors keep normal HTTP statuses and JSON bodies), then
opens `text/event-stream` and emits progress events while the pipeline runs. Closing the
connection (client cancel) aborts the pipeline and releases the embed lease.

**Output** — `200 text/event-stream` with `Cache-Control: no-cache` and
`X-Accel-Buffering: no`.

Event sequence:

| Event | Data | When |
|---|---|---|
| `progress` | `{ "phase": "extract" }` | extraction started |
| `progress` | `{ "phase": "batch", "index": 1, "total": 7 }` | before each embedding batch; `index` is 1-based, `total` is the number of batches |
| `progress` | `{ "phase": "verify" }` | LLM verification started |
| `done` | full `PageMatchOut` JSON (same fields as 11.3) | success, last event |
| `error` | `{ "code": "...", "message": "...", "status": 502 }` | failure **inside** the stream (e.g. `QUOTA_EXCEEDED`, `AI_UNAVAILABLE`, `PAGE_NO_CONTENT`) |

Example wire format:

```
event: progress
data: {"phase": "extract"}

event: progress
data: {"phase": "batch", "index": 1, "total": 7}

event: done
data: {"mode": "segments", "match_ratio": 0.12, ...}
```

**Errors** — synchronous failures use the table in 11.3 (normal JSON + HTTP status). Failures
after the stream opened are reported as an `error` event with a `status` field; the HTTP status of
the connection stays `200`.

> The extension treats an `error` event's `status` as the error status (default `502`) and a
> stream that ends without `done`/`error` as `NETWORK_ERROR`.

---

## 12. Chat (RAG, SSE)

Retrieval-augmented answers over the user's own notes. One request = one SSE stream. The
extension opens it from the background worker and forwards events to the side panel; pressing
"Stop" or closing the panel aborts the request.

### 12.1 `POST /api/v1/ai/chat`

**Input** — `ChatIn`

| Field | Type | Required | Constraints |
|---|---|---|---|
| `question` | string | **yes** | 1..2000 chars |
| `folder_id` | uuid \| null | no | restrict retrieval to one folder |
| `history` | `ChatTurnIn[]` | no | at most 20 items |
| `history[].role` | string | yes | `user` or `assistant` |
| `history[].content` | string | yes | ≤ 8000 chars |

The extension builds `history` from the last **5** completed question/answer pairs
(`MAX_HISTORY_PAIRS = 5`), skipping empty or still-streaming answers.

**Process — before streaming (`prepare`)**

1. Strip NUL/whitespace from the question. Empty → `400 CHAT_INPUT_INVALID`;
   longer than 2,000 → `413 CHAT_INPUT_TOO_LONG`.
2. Retrieve sources with the shared search routine (`rag_retrieve` quota operation): up to
   **5 sources**, 3 notes per source, best chunk per note.
3. Flatten by rank and clip the context to 18,000 characters (`CHAT_CONTEXT_MAX_CHARS`).
4. Build the citation list. `index` is continuous per note (1, 2, 3…), `source_index` is the
   source rank (1..5), and `source_domain` is the domain or `null`.
5. Open the generation quota lease with the estimated prompt + output tokens.

**Process — streaming**

- If no sources were found, the stream emits a refusal delta (the no-context answer) and then
  `done` with `tokens_used = 0`.
- Otherwise: `sources` first, then repeated `delta`s with generated text, then `done` with the
  committed token count.
- If the client disconnects, generation stops and only the generated portion is charged.

**Output** — `200 text/event-stream` (`Cache-Control: no-cache`, `X-Accel-Buffering: no`).

| Event | Data | Notes |
|---|---|---|
| `sources` | array of `ChatSource` | always the first event |
| `delta` | `{ "text": "..." }` | repeated, incremental answer text |
| `done` | `{ "tokens_used": 137 }` | normal completion |
| `error` | `{ "code": "...", "message": "..." }` | AI failure mid-stream; quota settled for what was generated |

`ChatSource` fields:

| Field | Type | Notes |
|---|---|---|
| `index` | integer | citation number used as `[n]` in the answer; continuous per note |
| `source_index` | integer | source group 1..5 |
| `source_domain` | string \| null | domain of the source; `null` = unknown source |
| `note_id` | uuid | note id |
| `chunk_id` | uuid | chunk id |
| `title` | string \| null | note title |
| `url` | string \| null | note URL |
| `snippet` | string | matching excerpt |

Example:

```
event: sources
data: [{"index":1,"source_index":1,"source_domain":"example.com","note_id":"…","chunk_id":"…","title":"…","url":"…","snippet":"…"}]

event: delta
data: {"text":"According to your notes, "}

event: delta
data: {"text":"…"}

event: done
data: {"tokens_used":137}
```

**Errors** — failures **before** the stream opens are normal JSON errors:

| HTTP | Code | Condition |
|---|---|---|
| 400 | `CHAT_INPUT_INVALID` | empty question |
| 402 | `QUOTA_EXCEEDED` | not enough tokens for retrieval/generation |
| 413 | `CHAT_INPUT_TOO_LONG` | question above 2,000 chars |
| 422 | `VALIDATION_ERROR` | schema violation (history limits, roles) |
| 429 | `RATE_LIMITED` | `ai` bucket (default 10/min) |
| 502 | `AI_UNAVAILABLE` | embedding failure during retrieval |

Failures **after** the stream opens arrive as an `error` event (HTTP status remains `200`).

---

## 13. Asynchronous note indexing

Creating, updating the content of, moving or deleting a note enqueues a
`semantic_search.index_note` job in the same database transaction. A separate worker process
(`python -m quickassist.worker`) performs chunking, embedding and pgvector writes.

### 13.1 Status transitions

| Status | Meaning | How it is set |
|---|---|---|
| `PROCESSING` | queued or running | on create, content change, folder move, reindex, or rebuild |
| `READY` | chunks and vectors are current | job completed; content unchanged re-runs only refresh `folder_id` and **do not** spend quota |
| `SKIPPED` | indexing skipped because the quota was exhausted | job detected insufficient quota; **no tokens are charged** |
| `FAILED` | permanent failure | provider error that will not recover after retries; the user can call `POST /notes/{id}/reindex` |

Temporary provider failures leave the note in `PROCESSING` and the job is retried. A deleted note
causes the worker to remove its chunks.

### 13.2 Embedding dimension rules

- The canonical vector dimension is **1536**.
- Providers returning more than 1536 dimensions are rejected; shorter vectors (e.g. 768) are
  zero-padded to 1536 by the embedding wrapper.
- Changing the embedding fingerprint (provider/base URL/model/dimension) triggers a rebuild:
  affected notes return to `PROCESSING`, and jobs carry the fingerprint they were created with.
  A job whose fingerprint no longer matches the current configuration is discarded, because a
  newer rebuild has already enqueued replacement jobs.

### 13.3 Evaluation implication

`POST /notes` returns before indexing finishes. A test that searches or chats immediately after
ingestion must poll `GET /notes/{id}` until `index_status` is `READY` (or fail fast on `FAILED`),
and must ensure the worker is running. `steady_evaluation` already implements this wait.

---

## 14. Client behaviours worth emulating

These behaviours belong to the extension, not the server, but they are part of how the API is
used and matter when an evaluation drives the backend the same way.

### 14.1 Single gateway

Only the background service worker issues HTTP requests. UI pages and content scripts call it via
`chrome.runtime` messages (RPC) or a `Port` for streaming chat. The token never leaves the
background context, and URL construction exists in exactly one file
(`shared/api/endpoints.ts`).

### 14.2 Token storage and refresh

- Access token: `chrome.storage.session` with `expiresAt = now + expires_in × 1000`.
- Refresh token: `chrome.storage.local`, so login survives a browser restart.
- Refresh is **single-flight**: concurrent requests that all receive `401 TOKEN_EXPIRED` trigger
  one refresh call; the others wait, then retry once.
- A refresh failure clears both tokens and signs the user out.

### 14.3 Outbox for note creation

1. On "quick note", the note body is written to an IndexedDB **outbox** immediately with
   `notBefore = now + 5000 ms` (the undo window) and an `Idempotency-Key` equal to the outbox item
   UUID.
2. After the window, the outbox is flushed; the server call is `POST /notes`.
3. On success, the note is removed from the outbox and inserted into the local cache.
4. On failure, the item stays queued (or moves to a "failed" store):
   - `401`/`TOKEN_MISSING` → failed (requires login before resending);
   - retryable errors (network, `429`, `5xx`, status `0`) → exponential backoff
     `10 s × 2^attempts`, capped at 15 minutes, up to 8 attempts;
   - `404 FOLDER_NOT_FOUND` with a `folder_id` → the folder is dropped and the note is retried
     immediately, landing in Inbox;
   - any other non-retryable error → failed store, where the user can retry or discard.
5. A periodic alarm (1 minute) retries due items. Nothing is ever silently discarded.

### 14.4 Incremental sync

- `GET /notes?updated_since=<max updated_at seen>&limit=200`, following `next_cursor` until
  `null`.
- `updated_since` makes the server include tombstones; `deleted_at != null` removes the note from
  the local cache.
- The stored watermark is the maximum `updated_at`, compared as parsed timestamps (not strings).
- Sync is single-flight; the notes list is served cache-first from IndexedDB and refreshed in the
  background.

### 14.5 Error handling and retries

- `AppError.retryable` is `true` for status `0` (network), `429` and `5xx`.
- `402 QUOTA_EXCEEDED` is never retried automatically.
- `409 NOTE_VERSION_CONFLICT` is surfaced to the user (reload and reconcile); `details.current_version`
  tells the UI the server's version.
- `429` waits for `details.retry_after`/`Retry-After` and shows the seconds to the user.

### 14.6 Cancellation

- Chat and page-match hold an `AbortController`. Stopping aborts the `fetch`, which the server
  observes as a disconnect: chat charges only the generated tokens, page match releases the
  embedding reservation.
- Page-match runs are tracked by a client-generated `requestId` so they can be cancelled
  individually.

---

## 15. Environment knobs for evaluation

All of these are backend settings (`apps/api/src/quickassist/infrastructure/config.py`) and can be
set through environment variables.

| Setting | Default | Effect |
|---|---|---|
| `APP_ENV` | `dev` in local compose | with `ENABLE_DEV_LOGIN=true` enables `POST /auth/dev-login` |
| `ENABLE_DEV_LOGIN` | `true` in local compose | see above |
| `AUTH_MODE` | `google` | `local` = single-user self-host; the server ignores client emails on dev-login |
| `LOCAL_AUTH_EMAIL` | — | fixed account used when `AUTH_MODE=local` |
| `AI_PROVIDER` | `mock` in local compose | `mock` exercises the API without external AI calls; `openai`/`gemini` use real providers |
| `MAX_NOTE_CHARS` | `20000` | note content limit (`NOTE_TOO_LONG`) |
| `MAX_SUMMARY_INPUT_CHARS` | `30000` | summary input limit (`SUMMARY_INPUT_TOO_LONG`) |
| `QUOTA_DEFAULT_TOKENS` | `1000000` | initial quota per user |
| `SEARCH_MAX_SOURCES` | `5` | default/top sources for library search |
| `SEARCH_NOTES_PER_SOURCE` | `10` | notes per source |
| `SEARCH_MIN_SIMILARITY` | `0.5` | vector threshold |
| `SEARCH_MIN_RRF` | `0.03` | hybrid-score threshold |
| `SEARCH_CANDIDATE_K` | `30` | candidate depth before grouping |
| `PAGE_MATCH_MAX_HTML_BYTES` | `2000000` | HTML size cap (`PAGE_TOO_LONG`) |
| `PAGE_MATCH_MAX_CHARS` | `50000` | scan cap unless `scan_all=true` |
| `PAGE_MATCH_MAX_BLOCK_CHARS` | `1200` | block size |
| `PAGE_MATCH_EMBED_BATCH_BLOCKS` | `32` | blocks per embedding batch |
| `PAGE_MATCH_MIN_CONFIDENCE` | `0.5` | result threshold |
| `PAGE_MATCH_FALLBACK_MIN_SIMILARITY` | `0.5` | cosine threshold when verification degrades |
| `RATE_LIMIT_SEARCH_PER_MINUTE` | `30` | `search` bucket |
| `RATE_LIMIT_AI_PER_MINUTE` | `10` | `ai` bucket |
| `RATE_LIMIT_WRITE_PER_MINUTE` | `120` | `write` bucket |
| `RATE_LIMIT_PAGE_MATCH_PER_MINUTE` | `6` | `page_match` bucket |
| `RATE_LIMIT_AI_SETTINGS_TEST_PER_MINUTE` | `6` | `ai_settings_test` bucket |
| `AI_BASE_URL_ALLOWLIST` | empty | CSV of allowed prefixes for BYOK `base_url`; empty = any `http(s)` |
| `AI_KEY_SECRET` | derived from `JWT_SECRET` when empty | AES-GCM key for BYOK secrets |
| `AI_EMBED_BATCH_TOKENS` | see config | token budget per embedding request |

Operational prerequisites for a realistic run:

1. PostgreSQL 16 with pgvector reachable (`GET /health/ready` returns `{"status":"ok","db":"ok"}`);
2. the worker running, otherwise notes stay `PROCESSING`;
3. a valid credential (dev-login or a token pair from a real login);
4. per-run data isolation by folder (`folder_id` on notes, `search`, `chat`) because dev-login
   reuses the same user, or cleanup with `POST /notes/bulk-delete` / `DELETE /me`.

---

## 16. Enum and limit reference

### 16.1 Enums

| Context | Values |
|---|---|
| `auth_mode` | `google`, `local` |
| `mode` (AI settings) | `inherit`, `byok` |
| `provider` (AI settings in/out) | `openai`, `gemini` |
| `server_default.provider` | `openai`, `gemini`, `mock` |
| `billing_mode` | `server`, `byok` |
| `index_status` | `PROCESSING`, `READY`, `SKIPPED`, `FAILED` |
| `ChatTurnIn.role` | `user`, `assistant` |
| `PageMatchOut.mode` | `segments`, `full_page` |
| `PageMatchOut.warning` | `VERIFY_UNAVAILABLE`, `null` |
| page-match SSE `phase` | `extract`, `batch`, `verify` |
| `AISTestOut.stage` | `embedding`, `chat` |

### 16.2 Limits

| Value | Limit |
|---|---|
| Note content | 20,000 chars |
| Note title | 500 chars |
| Note URL | 2,083 chars (valid URI) |
| Saved summary | 10,000 chars |
| Summary input | 30,000 chars |
| Folder name | 1..100 chars |
| Search query | 1..1,000 chars |
| Search `max_sources` | 1..20 (default 5) |
| Chat question | 2,000 chars |
| Chat history | 20 turns; 8,000 chars per turn |
| Chat sources | 5 |
| Chat context | 18,000 chars |
| Page-match query | 1..500 chars |
| Page-match HTML | 2,000,000 bytes |
| Page-match scan cap | 50,000 chars (unless `scan_all=true`) |
| Page-match block | 1,200 chars |
| Page-match embed batch | 32 blocks |
| Bulk note ids | 1..200 |
| `Idempotency-Key` | 100 chars |
| Refresh token | 20..256 chars |
| OAuth `code` | 1..2,048 chars |
| PKCE verifier | 43..128 chars |
| OAuth `nonce` | 16..128 chars |
| Dev-login email | 320 chars |
| `base_url` (BYOK) | 512 chars |
| `api_key` (BYOK) | 4,096 chars |
| Model names | 100 chars |
| `embedding_dim` | 1..100,000 (canonical 1,536) |
| `timeout_seconds` | 5..600 |

### 16.3 Error codes by HTTP status

| HTTP | Codes documented in this reference |
|---|---|
| 400 | `SUMMARY_INPUT_INVALID`, `CHAT_INPUT_INVALID`, `AI_CONFIG_INVALID`, `BAD_REQUEST` |
| 401 | `TOKEN_MISSING`, `TOKEN_EXPIRED`, `TOKEN_INVALID`, `REFRESH_INVALID`, `REFRESH_REUSED`, `REFRESH_EXPIRED`, `UNAUTHORIZED` |
| 402 | `QUOTA_EXCEEDED` |
| 403 | `DEV_LOGIN_DISABLED`, `RESET_NOT_ALLOWED`, `FORBIDDEN` |
| 404 | `NOTE_NOT_FOUND`, `FOLDER_NOT_FOUND`, `NOT_FOUND` |
| 409 | `NOTE_VERSION_CONFLICT`, `IDEMPOTENCY_KEY_REUSED`, `FOLDER_EXISTS`, `FOLDER_IS_DEFAULT`, `CONFLICT` |
| 413 | `NOTE_TOO_LONG`, `SUMMARY_INPUT_TOO_LONG`, `PAGE_TOO_LONG`, `CHAT_INPUT_TOO_LONG`, `PAYLOAD_TOO_LARGE` |
| 422 | `VALIDATION_ERROR`, `PAGE_NO_CONTENT`, `PAGE_MATCH_QUERY_INVALID`, `UNPROCESSABLE` |
| 429 | `RATE_LIMITED` (+ `Retry-After`) |
| 500 | `INTERNAL_ERROR` |
| 502 | `AI_UNAVAILABLE`, `OAUTH_UPSTREAM`, `UPSTREAM_ERROR` |

---

## Appendix A — Field reference

### A.1 `TokenPairOut`

| Field | Type | Required |
|---|---|---|
| `access_token` | string | yes |
| `refresh_token` | string | yes |
| `expires_in` | integer (seconds) | yes |
| `token_type` | string (default `Bearer`) | no |
| `is_new_user` | boolean (default `false`) | no |

### A.2 `NoteOut`

| Field | Type | Required |
|---|---|---|
| `id` | uuid | yes |
| `folder_id` | uuid | yes |
| `url` | string \| null | yes (nullable) |
| `domain` | string \| null | yes (nullable) |
| `title` | string \| null | yes (nullable) |
| `content` | string | yes |
| `summary_text` | string \| null | yes (nullable) |
| `index_status` | enum | yes |
| `version` | integer | yes |
| `created_at` | date-time | yes |
| `updated_at` | date-time | yes |
| `deleted_at` | date-time \| null | yes (nullable) |

### A.3 `QuotaOut` and `FolderOut`

`QuotaOut`: `limit_tokens`, `used_tokens`, `reserved_tokens`, `remaining_tokens` (integers),
`billing_mode` (`server`/`byok`) — all required — and `limit_enforced` (boolean, default `true`;
`false` only in dev unlimited mode).

`FolderOut`: `id` (uuid), `name` (string), `is_default` (boolean), `created_at`, `updated_at`
(date-time) — all required.

### A.4 `AISettingsOut`

| Field | Type | Required |
|---|---|---|
| `mode` | `inherit` \| `byok` | yes |
| `provider` | `openai` \| `gemini` \| null | no |
| `base_url` | string \| null | no |
| `chat_model` | string \| null | no |
| `embedding_model` | string \| null | no |
| `has_key` | boolean (default `false`) | no |
| `key_hint` | string \| null | no |
| `timeout_seconds` | number \| null | no |
| `server_default` | `ServerDefaultOut` | yes |
| `rebuild` | `AIRebuildOut` \| null | no |
| `rebuild_note_count` | integer (default `0`) | no |

`ServerDefaultOut`: `provider` (`openai`/`gemini`/`mock`), `chat_model`, `embedding_model` — all
required.

`AIRebuildOut`: `required` (boolean), `notes` (integer) — both required.
