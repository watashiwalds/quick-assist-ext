"""§0–§1 — Cấu hình và cổng kết nối tới backend QuickAssist chạy ĐẦY ĐỦ.

Điểm khác biệt căn bản so với quickassist_ai_evaluation (harness v2):
  - Gọi FastAPI qua HTTP thật (không import service) → PostgreSQL + pgvector,
    hybrid SQL, quota RESERVE→COMMIT, rate limit đều là code chạy thật.
  - Đăng nhập bằng POST /auth/dev-login (chỉ khi APP_ENV=dev|test và
    ENABLE_DEV_LOGIN=true) hoặc dùng sẵn access token qua env.

File này là CỔNG DUY NHẤT pipeline nói chuyện với hệ thống — phần còn lại
không biết gì về HTTP. Mỗi lời gọi đều trả kèm thời gian đo tại lớp HTTP.

Lưu ý dev-login: cùng một email sẽ trả về CÙNG user (sub = ``dev:<email>``),
không tạo kho mới. Vì vậy pipeline tạo **thư mục riêng cho từng run** và truyền
``folder_id`` vào notes/search/chat để cô lập corpus (xem SteadyConfig.folder_mode).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

# ============================================================ §0. Cấu hình


def load_env(path: Path) -> dict[str, str]:
    """Đọc .env tối giản (KEY=VALUE, bỏ comment); biến OS cùng tên được ưu tiên.

    Nhờ vậy CI có thể đặt ``STEADY_*`` trực tiếp mà không cần ghi file .env.
    """
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        if key.startswith("STEADY_"):
            env[key] = value
    return env


@dataclass
class SteadyConfig:
    """Toàn bộ tham số của một lần chạy — runner dựng từ CLI + .env."""

    api_base_url: str = "http://localhost:8000/api/v1"
    email: str = "steady-eval@quickassist.local"  # user riêng cho đánh giá
    access_token: str = ""                        # ưu tiên nếu đặt (bỏ qua dev-login)
    dataset_dir: Path = field(default_factory=lambda: Path("dataset"))
    modules: list[str] = field(default_factory=lambda: ["search", "rag", "pagematch"])
    top_k: int = 5                   # số NOTE đầu tiên dùng để chấm Recall/MRR/AnswerHit
    max_sources: int = 5             # SearchIn.max_sources (1..20) — số NGUỒN/domain API trả
    pagematch_top_k: int = 5
    model_label: str = "unlabeled"                # nhãn tổ hợp LLM + embedding của run này
    tag: str = ""
    # --- cô lập corpus ---
    folder_mode: str = "run"         # "run" = thư mục riêng mỗi run; "shared" = Inbox
    fresh_notes: bool = False        # True → idempotency key theo run → tạo note mới mỗi run
    cleanup_notes: bool = False      # True → xoá note + thư mục của run sau khi chấm xong
    allow_partial: bool = False      # True → vẫn chạy dù dataset còn dòng lỗi/bị loại
    allow_degraded: bool = False     # True → vẫn chấm dù có note chưa READY
    # --- thời gian / tần suất ---
    request_timeout_s: float = 30.0
    chat_timeout_s: float = 120.0
    pagematch_timeout_s: float = 90.0
    wait_index_timeout_s: float = 120.0
    poll_interval_s: float = 1.0
    max_retries_429: int = 5
    # --- phản chiếu giới hạn backend (cắt trước ở máy) ---
    max_note_chars: int = 20_000     # MAX_NOTE_CHARS
    max_html_bytes: int = 2_000_000  # PAGE_MATCH_MAX_HTML_BYTES
    max_query_chars: int = 500       # MAX_QUERY_CHARS (page-match, chặt nhất)
    # --- metadata tái lập (không tự phát hiện được từ HTTP health) ---
    provider: str = ""
    model: str = ""
    embedding_model: str = ""
    temperature: str = ""
    evaluator: str = ""
    evidence_type: str = "auto"      # auto | smoke | quality | failure
    dataset_version: str = ""


# ============================================================ §1. Kết nối backend


class ApiError(RuntimeError):
    """Lỗi HTTP từ backend — giữ nguyên code/message chuẩn của hệ thống."""

    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(f"HTTP {status} {code}: {message}")
        self.status, self.code, self.message, self.details = status, code, message, details or {}


@dataclass
class StreamResult:
    """Kết quả một luồng SSE (/ai/chat)."""

    events: list[tuple[str, dict]]  # [(type, data), ...] theo thứ tự nhận được
    first_event_ms: float
    total_ms: float

    def of(self, event_type: str) -> list[dict]:
        return [data for t, data in self.events if t == event_type]


class BackendClient:
    """Ủy quyền HTTP cho mọi chức năng: auth, folder, notes, search, chat SSE, page-match, quota."""

    def __init__(self, cfg: SteadyConfig):
        self.cfg = cfg
        self._client = httpx.Client(base_url=cfg.api_base_url, timeout=cfg.request_timeout_s)
        self.access_token: str = cfg.access_token
        self.refresh_token: str = ""
        self.expires_at: float = 0.0  # epoch giây; 0 = không biết

    # ---------- vòng đời ----------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BackendClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # ---------- xác thực ----------
    def login(self) -> None:
        """Dev-login (APP_ENV=dev|test + ENABLE_DEV_LOGIN=true) hoặc dùng token có sẵn."""
        if self.access_token:
            return
        t0 = time.perf_counter()
        status, body, _ = self.json("POST", "/auth/dev-login", payload={"email": self.cfg.email})
        if status != 200:
            raise ApiError(status, "LOGIN_FAILED", f"dev-login thất bại: {body}")
        self._store_tokens(body)
        print(f"[auth] dev-login ok ({(time.perf_counter() - t0) * 1000:.0f} ms) — user {self.cfg.email}")

    def _store_tokens(self, body: dict) -> None:
        self.access_token = body.get("access_token", "")
        self.refresh_token = body.get("refresh_token", self.refresh_token)
        try:
            self.expires_at = time.time() + float(body.get("expires_in", 0) or 0)
        except (TypeError, ValueError):
            self.expires_at = 0.0

    def refresh(self) -> None:
        """Xoay token qua POST /auth/refresh (API_REFERENCE §4.3).

        Access token sống ngắn (mặc định 900 s); run dài vượt hạn sẽ nhận 401
        ``TOKEN_EXPIRED``. Client tự refresh một lần rồi thử lại request.
        """
        if not self.refresh_token:
            raise ApiError(401, "TOKEN_EXPIRED",
                           "access token hết hạn nhưng không có refresh token")
        resp = self._client.post("/auth/refresh", json={"refresh_token": self.refresh_token})
        body = self._decode(resp)
        if resp.is_error or not body:
            # Refresh thất bại → xoá phiên cục bộ, không thử lại vô hạn.
            self.access_token = ""
            self.refresh_token = ""
            self.expires_at = 0.0
            self._raise(resp.status_code, body, resp.text)
        self._store_tokens(body)
        print("[auth] đã refresh access token")

    # ---------- helpers ----------
    def _headers(self, idempotency_key: str | None = None,
                 sse: bool = False) -> dict[str, str]:
        headers: dict[str, str] = {}
        if sse:
            headers["Accept"] = "text/event-stream"
        if self.access_token:  # health/live gọi trước khi login → không gửi header rỗng
            headers["Authorization"] = f"Bearer {self.access_token}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    @staticmethod
    def _raise(status: int, body: dict | list | None, raw_text: str = "") -> None:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        raise ApiError(status, err.get("code", "UNKNOWN"),
                       err.get("message") or raw_text[:300] or "phản hồi lỗi không có JSON",
                       err.get("details"))

    @staticmethod
    def _retry_after(resp: httpx.Response) -> float:
        raw = resp.headers.get("Retry-After", "")
        try:
            return max(0.0, float(raw))
        except ValueError:
            return 2.0

    def _decode(self, resp: httpx.Response) -> dict | list | None:
        if not resp.content:
            return None
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError):
            return None

    def json(self, method: str, path: str, *, payload: dict | None = None,
             idempotency_key: str | None = None, timeout: float | None = None
             ) -> tuple[int, dict | list | None, float]:
        """Gọi JSON thuần; trả (status, body, elapsed_ms).

        - 401 ``TOKEN_EXPIRED``: refresh token một lần rồi thử lại (API_REFERENCE §4.3).
        - 429: chờ theo ``Retry-After`` và thử lại tối đa ``max_retries_429`` lần
          (rate limit AI/PageMatch tính theo phút, nên một lần thử lại là không đủ).
        """
        t0 = time.perf_counter()
        attempts_429 = 0
        refreshed = False
        while True:
            kwargs: dict = {"json": payload, "headers": self._headers(idempotency_key)}
            if timeout is not None:  # timeout=None của httpx = TẮT timeout, không phải mặc định
                kwargs["timeout"] = timeout
            resp = self._client.request(method, path, **kwargs)
            body = self._decode(resp)
            code = body.get("error", {}).get("code", "") if isinstance(body, dict) else ""
            if resp.status_code == 401 and code == "TOKEN_EXPIRED" \
                    and not refreshed and self.refresh_token:
                self.refresh()
                refreshed = True
                continue
            if resp.status_code == 429 and attempts_429 < self.cfg.max_retries_429:
                wait = self._retry_after(resp)
                print(f"[rate-limit] 429 {path} — chờ {wait:.1f}s "
                      f"(lần {attempts_429 + 1}/{self.cfg.max_retries_429})")
                attempts_429 += 1
                time.sleep(wait)
                continue
            elapsed = (time.perf_counter() - t0) * 1000
            if resp.is_error:
                self._raise(resp.status_code, body, resp.text)
            if body is None and resp.content:
                raise ApiError(resp.status_code, "NON_JSON_RESPONSE",
                               f"phản hồi không phải JSON: {resp.text[:200]}")
            return resp.status_code, body, elapsed

    def sse(self, path: str, payload: dict) -> StreamResult:
        """POST nhận text/event-stream; gom sự kiện sources/delta/done/error theo thứ tự.

        Cùng chính sách với :meth:`json`: refresh một lần khi 401 ``TOKEN_EXPIRED``
        và retry 429 theo ``Retry-After`` (RAG/PageMatch bị hạn mức theo phút).
        """
        attempts_429 = 0
        refreshed = False
        while True:
            t0 = time.perf_counter()
            events: list[tuple[str, dict]] = []
            first_ms = 0.0
            retry: str | None = None  # "429" | "auth" | None
            wait = 0.0
            with self._client.stream("POST", path, json=payload,
                                     headers=self._headers(sse=True),
                                     timeout=self.cfg.chat_timeout_s) as resp:
                if resp.is_error:
                    raw = resp.read()
                    body = None
                    try:
                        body = json.loads(raw or b"{}")
                    except (json.JSONDecodeError, ValueError):
                        pass
                    code = body.get("error", {}).get("code", "") if isinstance(body, dict) else ""
                    if resp.status_code == 401 and code == "TOKEN_EXPIRED" \
                            and not refreshed and self.refresh_token:
                        retry = "auth"
                    elif resp.status_code == 429 and attempts_429 < self.cfg.max_retries_429:
                        wait = self._retry_after(resp)
                        print(f"[rate-limit] 429 {path} (SSE) — chờ {wait:.1f}s "
                              f"(lần {attempts_429 + 1}/{self.cfg.max_retries_429})")
                        attempts_429 += 1
                        retry = "429"
                    else:
                        self._raise(resp.status_code, body, raw.decode("utf-8", "replace"))
                else:
                    event_type, data_lines = "", []
                    for line in resp.iter_lines():
                        if first_ms == 0.0 and line.strip():
                            first_ms = (time.perf_counter() - t0) * 1000
                        if line.startswith("event:"):
                            event_type = line.split(":", 1)[1].strip()
                        elif line.startswith("data:"):
                            data_lines.append(line.split(":", 1)[1].strip())
                        elif not line.strip() and event_type:
                            raw = "\n".join(data_lines) or "{}"
                            try:
                                events.append((event_type, json.loads(raw)))
                            except json.JSONDecodeError:
                                events.append((event_type, {"raw": raw}))
                            event_type, data_lines = "", []
            if retry == "auth":
                self.refresh()
                refreshed = True
                continue
            if retry == "429":
                time.sleep(wait)
                continue
            total_ms = (time.perf_counter() - t0) * 1000
            return StreamResult(events, first_ms, total_ms)

    # ---------- chức năng hệ thống (hành trình người dùng thật) ----------
    def health(self) -> dict:
        _, body, _ = self.json("GET", "/health/live")
        return body or {}

    def ready(self) -> dict:
        _, body, _ = self.json("GET", "/health/ready")
        return body or {}

    def quota(self) -> dict:
        _, body, _ = self.json("GET", "/me/quota")
        return body or {}

    # ---------- thư mục (cô lập corpus theo run) ----------
    def list_folders(self) -> list[dict]:
        _, body, _ = self.json("GET", "/folders")
        if isinstance(body, list):  # API trả mảng trần
            return body
        if isinstance(body, dict):
            return body.get("items", [])
        return []

    def create_folder(self, name: str) -> dict:
        _, body, _ = self.json("POST", "/folders", payload={"name": name[:100]})
        return body or {}

    def find_or_create_folder(self, name: str) -> dict:
        wanted = name[:100]
        for folder in self.list_folders():
            if folder.get("name") == wanted:
                return folder
        try:
            return self.create_folder(wanted)
        except ApiError as exc:
            if exc.status != 409:  # có thể race với request khác → đọc lại
                raise
            for folder in self.list_folders():
                if folder.get("name") == wanted:
                    return folder
            raise

    def delete_folder(self, folder_id: str) -> None:
        self.json("DELETE", f"/folders/{folder_id}")

    # ---------- ghi chú ----------
    def create_note(self, content: str, title: str | None = None,
                    idempotency_key: str | None = None,
                    folder_id: str | None = None) -> tuple[int, dict, float]:
        payload: dict = {"content": content, "title": title}
        if folder_id:
            payload["folder_id"] = folder_id
        status, body, elapsed = self.json("POST", "/notes", payload=payload,
                                          idempotency_key=idempotency_key)
        return status, body or {}, elapsed

    def get_note(self, note_id: str) -> tuple[dict, float]:
        _, body, elapsed = self.json("GET", f"/notes/{note_id}")
        return body or {}, elapsed

    def count_notes(self, folder_id: str | None = None) -> int:
        """Đếm ghi chú trong một thư mục (phân trang) — tính sàn ngẫu nhiên cho search."""
        total, cursor = 0, None
        while True:
            path = "/notes?limit=200" + (f"&folder_id={folder_id}" if folder_id else "") \
                + (f"&cursor={cursor}" if cursor else "")
            _, body, _ = self.json("GET", path)
            total += len((body or {}).get("items", []))
            cursor = (body or {}).get("next_cursor")
            if not cursor:
                return total

    def bulk_delete_notes(self, note_ids: list[str]) -> int:
        _, body, _ = self.json("POST", "/notes/bulk-delete", payload={"ids": note_ids})
        return int((body or {}).get("deleted", 0))

    # ---------- tìm kiếm / RAG / PageMatch ----------
    def search(self, query: str, max_sources: int = 5,
               folder_id: str | None = None) -> tuple[list[dict], float]:
        """POST /search — trả về danh sách NGUỒN đã nhóm (SearchOut.sources).

        Contract hiện tại (API_REFERENCE §9.1): request dùng ``max_sources``
        (1..20), response là ``{sources:[{domain,label,source_rank,note_count,
        notes:[{note_id,title,url,summary,snippet,score,similarity}]}]}``.
        Flatten/top-k note do tầng flow quyết định.
        """
        payload: dict = {"query": query, "max_sources": max_sources}
        if folder_id:
            payload["folder_id"] = folder_id
        _, body, elapsed = self.json("POST", "/search", payload=payload)
        if isinstance(body, dict) and "sources" not in body and "items" in body:
            raise RuntimeError(
                "POST /search trả 'items[]' (contract cũ) — harness cần 'sources[]'. "
                "Kiểm tra phiên bản backend/API_REFERENCE.")
        return (body.get("sources", []) if isinstance(body, dict) else []), elapsed

    def page_match(self, query: str, html: str | None = None, text: str | None = None,
                   title: str | None = None) -> tuple[dict, float]:
        payload = {"query": query, "title": title}
        if html is not None:
            payload["html"] = html
        else:
            payload["text"] = text
        # Timeout riêng: page-match gồm extract + embed + LLM verify, có thể > 30s.
        _, body, elapsed = self.json("POST", "/ai/page-match", payload=payload,
                                     timeout=self.cfg.pagematch_timeout_s)
        return (body if isinstance(body, dict) else {}), elapsed

    def chat_sse(self, question: str, folder_id: str | None = None) -> StreamResult:
        payload: dict = {"question": question}
        if folder_id:
            payload["folder_id"] = folder_id
        return self.sse("/ai/chat", payload)