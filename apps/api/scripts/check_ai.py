"""Kiểm tra nhanh khoá + model AI đang cấu hình (embedding + tóm tắt 1 câu). Không in khoá.

    cd apps/api
    python scripts/check_ai.py                 # đọc cấu hình từ biến môi trường / apps/api/.env
    python scripts/check_ai.py --env ../../infra/.env
    python scripts/check_ai.py --env ../../infra/.env --try-both   # Gemini: thử cả AI Studio và Vertex

Thoát mã 0 nếu cả embedding và chat đều chạy được.
"""

import argparse
import asyncio
import sys
import time

# Model chat dự phòng khi model đang cấu hình lỗi (VD Gemma trả 500) — chỉ để chẩn đoán, không tự đổi.
FALLBACK_CHAT_MODELS = ["gemma-4-26b-a4b-it", "gemini-flash-latest"]

ENDPOINTS = {
    "AI Studio": "https://generativelanguage.googleapis.com/v1beta/models",
    "Vertex express": "https://aiplatform.googleapis.com/v1/publishers/google/models",
}


async def check(settings) -> bool:  # type: ignore[no-untyped-def]
    from quickassist.infrastructure.openai.base import ChatMessage

    if settings.ai_provider == "gemini":
        from quickassist.infrastructure.openai.gemini_client import GeminiClient

        ai = GeminiClient(settings)
    else:
        from quickassist.infrastructure.openai.openai_client import OpenAIClient

        ai = OpenAIClient(settings)
    ok = True
    try:
        t = time.perf_counter()
        e = await ai.embed(["Hà Nội là thủ đô của Việt Nam."])
        print(f"  ✓ embedding  {e.model}  {len(e.vectors[0])} chiều  {time.perf_counter() - t:.1f}s")
    except Exception as ex:  # noqa: BLE001
        ok = False
        print(f"  ✗ embedding  {type(ex).__name__}: {ex}")
    try:
        t = time.perf_counter()
        c = await ai.complete(
            [ChatMessage("system", "Bạn tóm tắt văn bản tiếng Việt thật ngắn gọn."),
             ChatMessage("user", "Tóm tắt trong 1 câu: Hà Nội là thủ đô, trung tâm chính trị và văn hoá "
                                 "của Việt Nam, nổi tiếng với hồ Hoàn Kiếm và phố cổ.")],
            max_tokens=200,
        )
        print(f"  ✓ chat       {c.model}  {c.usage.prompt_tokens}+{c.usage.completion_tokens} token  "
              f"{time.perf_counter() - t:.1f}s")
        print(f"    → {c.text.strip()[:200]}")
        if not c.text.strip():
            ok = False
            print("  ✗ chat trả về rỗng")
    except Exception as ex:  # noqa: BLE001
        ok = False
        print(f"  ✗ chat       {type(ex).__name__}: {ex}")
    finally:
        close = getattr(ai, "aclose", None)
        if close:
            await close()
    return ok


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", help="đường dẫn file .env (VD ../../infra/.env)")
    ap.add_argument("--try-both", action="store_true", help="Gemini: thử cả AI Studio và Vertex express")
    a = ap.parse_args()

    from quickassist.infrastructure.config import Settings

    base = Settings(_env_file=a.env) if a.env else Settings()  # type: ignore[call-arg]
    print(f"AI_PROVIDER={base.ai_provider}")
    if base.ai_provider == "mock":
        print("  AI_PROVIDER=mock → không gọi AI thật. Đặt AI_PROVIDER=gemini (hoặc openai) rồi chạy lại.")
        return 1

    targets = [(None, base.gemini_base_url if base.ai_provider == "gemini" else base.openai_base_url)]
    if a.try_both and base.ai_provider == "gemini":
        targets = list(ENDPOINTS.items())
    results = []
    for label, url in targets:
        s = base.model_copy(update={"gemini_base_url": url}) if base.ai_provider == "gemini" else base
        model = s.gemini_chat_model if s.ai_provider == "gemini" else s.chat_model
        print(f"\n[{label or 'cấu hình hiện tại'}] {url}  model={model}")
        results.append((url, await check(s)))
    good = [u for u, ok in results if ok]
    print()
    if good:
        if base.ai_provider == "gemini" and good[0] != base.gemini_base_url:
            print(f"→ Dùng được. Đặt GEMINI_BASE_URL={good[0]}")
        else:
            print("→ OK: khoá và model dùng được.")
        return 0
    if base.ai_provider == "gemini":
        for model in FALLBACK_CHAT_MODELS:
            if model == base.gemini_chat_model:
                continue
            s = base.model_copy(update={"gemini_chat_model": model})
            print(f"\n[thử model khác] {s.gemini_base_url}  model={model}")
            if await check(s):
                print(f"\n→ Dùng được với model khác. Đặt GEMINI_CHAT_MODEL={model}")
                return 0
    print("→ Lỗi. Gợi ý: http 400/403 = khoá sai loại hoặc chưa bật API; http 404 = sai tên model "
          "(xem danh sách model trên AI Studio); với khoá Vertex express thử --try-both.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
