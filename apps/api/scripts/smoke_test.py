"""H07 — smoke test môi trường demo/RC (chạy sau mỗi lần deploy, < 1 phút).

    python scripts/smoke_test.py --base https://api.quickassist.example.com
    python scripts/smoke_test.py --base http://localhost:8000 --dev-login      # môi trường dev
    # prod (không có dev-login): lấy access token từ extension đã đăng nhập
    SMOKE_ACCESS_TOKEN=<access token> python scripts/smoke_test.py --base https://...

Kiểm: health, header bảo mật, 401 khi thiếu token, tạo ghi chú (idempotent) → worker index READY
→ tìm thấy → tóm tắt preview → xoá ghi chú. Thoát mã 1 nếu có bước lỗi. Không in token/nội dung.
"""

import argparse
import os
import sys
import time
import uuid

import httpx

# Windows can default to the cp1252 console encoding.  This script reports
# Vietnamese labels and symbols, so force UTF-8 instead of crashing on output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OK, FAIL = "✅", "❌"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--dev-login", action="store_true")
    ap.add_argument("--timeout", type=float, default=60)
    a = ap.parse_args()
    api = a.base.rstrip("/") + "/api/v1"
    results: list[tuple[str, bool, str]] = []

    def check(name: str, cond: bool, info: str = "") -> bool:
        results.append((name, cond, info))
        print(f"{OK if cond else FAIL} {name} {info}")
        return cond

    # Gemini generation may take longer than the old fixed 20-second timeout.
    # Reuse --timeout for HTTP calls and for waiting on the indexing worker.
    with httpx.Client(timeout=a.timeout) as c:
        r = c.get(f"{api}/health/ready")
        check("health/ready", r.status_code == 200 and r.json().get("db") == "ok", f"({r.status_code})")
        check("header bảo mật", r.headers.get("x-content-type-options") == "nosniff"
              and "x-request-id" in r.headers)
        r = c.get(f"{api}/notes")
        check("401 khi thiếu token", r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_MISSING")

        token = os.environ.get("SMOKE_ACCESS_TOKEN")
        if a.dev_login:
            r = c.post(f"{api}/auth/dev-login", json={"email": f"smoke-{uuid.uuid4().hex[:8]}@test.local"})
            if check("dev-login", r.status_code == 200, f"({r.status_code})"):
                token = r.json()["access_token"]
        if not token:
            print("— bỏ qua phần có xác thực (đặt SMOKE_ACCESS_TOKEN hoặc --dev-login)")
            return 0 if all(ok for _, ok, _ in results) else 1
        h = {"Authorization": f"Bearer {token}"}

        marker = f"smoke{uuid.uuid4().hex[:10]}"
        body = {"content": f"Kiểm thử khói QuickAssist {marker}: pgvector tìm kiếm ngữ nghĩa.",
                "title": "Smoke test", "url": "https://example.com/smoke"}
        key = {"Idempotency-Key": str(uuid.uuid4())}
        t0 = time.perf_counter()
        r1 = c.post(f"{api}/notes", json=body, headers=h | key)
        save_ms = (time.perf_counter() - t0) * 1000
        r2 = c.post(f"{api}/notes", json=body, headers=h | key)
        ok = check("tạo ghi chú < 2s", r1.status_code == 201 and save_ms < 2000, f"({save_ms:.0f} ms)")
        check("idempotent", ok and r2.json()["id"] == r1.json()["id"])
        if not ok:
            return 1
        nid = r1.json()["id"]

        status, deadline = "PROCESSING", time.time() + a.timeout
        while status == "PROCESSING" and time.time() < deadline:
            time.sleep(1)
            status = c.get(f"{api}/notes/{nid}", headers=h).json()["index_status"]
        check("worker index → READY", status == "READY", f"({status})")

        t0 = time.perf_counter()
        r = c.post(f"{api}/search", json={"query": marker}, headers=h)
        search_ms = (time.perf_counter() - t0) * 1000
        found = r.status_code == 200 and any(i["note_id"] == nid for i in r.json()["items"])
        check("tìm thấy ghi chú < 3s", found and search_ms < 3000, f"({search_ms:.0f} ms)")
        r = c.post(f"{api}/ai/summaries", json={"note_id": nid}, headers=h)
        check("tóm tắt preview", r.status_code == 200 and bool(r.json().get("summary")), f"({r.status_code})")
        r = c.delete(f"{api}/notes/{nid}", headers=h)
        check("xoá ghi chú", r.status_code == 204)
        q = c.get(f"{api}/me/quota", headers=h)
        check("quota", q.status_code == 200 and q.json()["reserved_tokens"] == 0)

    failed = [n for n, ok, _ in results if not ok]
    summary = f"\n{len(results) - len(failed)}/{len(results)} bước đạt"
    print(summary + (f" — LỖI: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
