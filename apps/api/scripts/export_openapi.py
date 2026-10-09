"""P02 — xuất OpenAPI (nguồn sự thật của contract) ra docs/api/openapi.json.

    cd apps/api && python scripts/export_openapi.py          # ghi file
    cd apps/api && python scripts/export_openapi.py --check  # CI: báo lỗi nếu file lệch code
Extension sinh kiểu TypeScript từ file này: cd apps/extension && npm run gen:api:file
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/api/src"))
os.environ.setdefault("APP_ENV", "dev")
os.environ["ENABLE_DEV_LOGIN"] = "false"  # route dev-login không nằm trong contract

from quickassist.main import create_app  # noqa: E402

OUT = ROOT / "docs/api/openapi.json"


def render() -> str:
    spec = create_app().openapi()
    spec["servers"] = [{"url": "http://localhost:8000", "description": "Dev (docker compose)"}]
    return json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            sys.exit("docs/api/openapi.json lệch với code — chạy: python scripts/export_openapi.py")
        print("openapi.json khớp code")
    else:
        OUT.write_text(text, encoding="utf-8")
        print(f"đã ghi {OUT.relative_to(ROOT)}")
