# ⑤ Infrastructure Layer

Hạ tầng dùng chung, **không có nghiệp vụ**. Mọi tầng được import; tầng này không import `presentation`, `business`, `data_access` (test L1).

```
infrastructure/
├─ config.py            Settings (pydantic-settings, đọc .env)
├─ logging.py           log JSON + request_id; không log token/nội dung ghi chú
├─ request_context.py   request_id theo contextvar
├─ security.py          JWT access token, băm refresh token
├─ errors.py            lỗi kỹ thuật (dịch vụ ngoài lỗi, timeout)
├─ google_oauth/        OIDC client: đổi code + PKCE, xác minh id_token
├─ openai/              AI Adapter: base.py (interface) · openai_client.py · mock_client.py
└─ jobs/                hàng đợi job trên PostgreSQL (SKIP LOCKED), retry/backoff; job_kinds.py
```

**Thêm nhà cung cấp mới** (vd. AI khác): viết class cài interface trong `openai/base.py`, chọn bằng biến `AI_PROVIDER` trong `openai/__init__.py`. Business không đổi (ADR-0004).

Secret (client_secret, API key, JWT_SECRET) chỉ đọc từ biến môi trường — không hard-code, không gửi về extension.
