#!/usr/bin/env bash
# Khởi động llama-server ở router mode: 2 model (chat + embedding) trên CÙNG 1 cổng 8080.
# Router tự load model theo trường "model" của request, mỗi model chạy 1 process riêng.
#
# Dùng:  ./local_infer/run-router.sh          (chạy foreground)
#        ./local_infer/run-router.sh -d      (background, log ở local_infer/router.log)
#
# Đổi binary:  LLAMA_SERVER=/path/to/llama-server ./local_infer/run-router.sh
# Chỉ bind localhost (backend chạy trực tiếp, không Docker):
#              BIND_HOST=127.0.0.1 ./local_infer/run-router.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLAMA_SERVER="${LLAMA_SERVER:-./llama-server}"   # mặc định như lệnh hiện tại của bạn
PRESET="$HERE/models-preset.ini"
PORT="${PORT:-8080}"
LOG="$HERE/router.log"

[[ -x "$LLAMA_SERVER" || -n "$(command -v "$LLAMA_SERVER")" ]] || {
  echo "❌ Không tìm thấy llama-server ($LLAMA_SERVER). Dùng: LLAMA_SERVER=/đường/dẫn ./run-router.sh"
  exit 1
}
[[ -f "$PRESET" ]] || { echo "❌ Thiếu preset: $PRESET"; exit 1; }

# Cảnh báo sớm nếu build quá cũ (không có router mode)
if "$LLAMA_SERVER" --help 2>&1 | grep -q -- '--models-preset'; then
  echo "✓ llama-server có router mode"
else
  echo "⚠ llama-server build này KHÔNG có --models-preset — cần build mới (cuối 2025+)"
  echo "  Xem: https://github.com/ggml-org/llama.cpp (cmake --build build -t llama-server)"
fi

echo "▶ Router: http://127.0.0.1:$PORT  (preset: $PRESET)"
echo "  Bind: ${BIND_HOST:-0.0.0.0} — container Docker truy cập qua IP của host"
echo "  Mỗi model chạy 1 process con; alias: chat / embed — list: curl :$PORT/models"

if [[ "${1:-}" == "-d" ]]; then
  nohup "$LLAMA_SERVER" \
    --host "${BIND_HOST:-0.0.0.0}" --port "$PORT" \
    --models-preset "$PRESET" \
    --models-max 2 \
    --api-key local \
    --log-verbosity 4 \
    >"$LOG" 2>&1 &
  echo "▶ Đã chạy nền (PID $!). Log: $LOG"
  echo "  Dừng: kill $!   # hoặc: pkill -f 'models-preset $PRESET'"
else
  exec "$LLAMA_SERVER" \
    --host "${BIND_HOST:-0.0.0.0}" --port "$PORT" \
    --models-preset "$PRESET" \
    --models-max 2 \
    --api-key local \
    --log-verbosity 2
fi
