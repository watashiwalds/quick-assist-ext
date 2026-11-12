# local_infer — 2 model (chat + embedding) trên 1 cổng 8080 bằng llama-server router mode

Thay 2 lệnh chạy riêng (cổng 8080 chat, 8081 embedding) bằng **1 server duy nhất**:
llama-server ở **router mode** — không truyền `-m` trực tiếp, mà đưa danh sách model vào
file preset INI. Router forward request theo trường `"model"` trong body, mỗi model
chạy trong process con riêng (một cái chết không ảnh hưởng cái kia), tự load/unload.

## 1. Khởi động

```bash
./local_infer/run-router.sh        # foreground
# hoặc nền:  ./local_infer/run-router.sh -d   (log: local_infer/router.log)
```

Yêu cầu llama.cpp build có router mode (cuối 2025+). Kiểm tra nhanh:

```bash
./llama-server --help | grep -- --models-preset
```

Nếu không có → build lại: `cmake -B build && cmake --build build -t llama-server`.

## 2. Kiểm tra server + từng model

```bash
curl -s http://127.0.0.1:8080/models | python3 -m json.tool   # thấy "chat" và "embed"

# Chat:
curl -s http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"chat","messages":[{"role":"user","content":"xin chào"}],"max_tokens":20}'

# Embedding:
curl -s http://127.0.0.1:8080/v1/embeddings -H 'Content-Type: application/json' \
  -d '{"model":"embed","input":["kiểm tra"]}' | head -c 300
```

## 3. Cấu hình `.env` của repo (infra/.env hoặc infra/.env.local)

```env
AI_PROVIDER=openai
OPENAI_API_KEY=local
;; backend KHÔNG chạy Docker: dùng 127.0.0.1. Nếu chạy qua Docker: dùng IP của host
;; (xem mục 3.1 ⚠), ví dụ http://192.168.1.50:8080/v1
OPENAI_BASE_URL=http://127.0.0.1:8080/v1
CHAT_MODEL=chat
EMBEDDING_MODEL=embed
EMBEDDING_DIM=1024
```

Ghi chú:

- `OPENAI_API_KEY=local` khớp `--api-key local` trong `run-router.sh` (đổi cùng nhau nếu muốn).
- **Qwen3-Embedding-0.6B trả vector 1024 chiều** → `EMBEDDING_DIM=1024`.
  DB hiện dùng cột `vector(1536)` (mặc định cho text-embedding-3-small) → cần 1 migration
  đổi cột sang `vector(1024)` rồi reindex các chunk cũ. Đây là bước duy nhất ngoài `.env`.
- Api code gửi kèm `"dimensions"` trong request; llama-server bỏ qua field lạ, không sao.

### 3.1. Áp dụng `.env` cho backend (Docker)

`api`, `worker` và `migrate` trong `infra/docker-compose.yml` đọc cấu hình từ `infra/.env`
qua `env_file` — sửa xong file phải **recreate** container để giá trị mới có hiệu lực:

```bash
# từ thư mục gốc repo
docker compose -f infra/docker-compose.yml up -d --force-recreate api worker
```

Ghi chú:

- Chỉ dùng `up -d api worker` cũng được ở bản docker compose mới (tự recreate khi
  nội dung `env_file` thay đổi), nhưng thêm `--force-recreate` là chắc chắn nhất.
- Không cần build lại image (`--build` chỉ cần khi đổi mã nguồn).
- Xem nhanh giá trị đã vào container:
  ```bash
  docker compose -f infra/docker-compose.yml exec api env | grep -E 'AI_|OPENAI_|EMBEDDING|CHAT_'
  ```
- Log backend nếu gọi AI lỗi: `docker compose -f infra/docker-compose.yml logs -f api worker`.
- ⚠ **Backend chạy qua Docker → không dùng `127.0.0.1` cho `OPENAI_BASE_URL`**:
  container không thấy `127.0.0.1` của host. Vì chọn bind llama-server ra ngoài
  (`0.0.0.0` — mặc định của `run-router.sh`), hãy trỏ vào **IP của host**:
  1. Lấy IP: `hostname -I | awk '{print $1}'` (ví dụ `192.168.1.50`);
  2. Đặt trong `.env`: `OPENAI_BASE_URL=http://192.168.1.50:8080/v1`;
  3. Recreate container như mục 3.1.
  Chỉ dùng trên mạng máy tin cậy — `0.0.0.0` mở cổng cho cả LAN (đã có `--api-key local`
  chặn lộ diện, nhưng không thay firewall). Chạy backend trực tiếp (không Docker) thì
  `BIND_HOST=127.0.0.1 ./local_infer/run-router.sh` + `OPENAI_BASE_URL=http://127.0.0.1:8080/v1`.

## 4. Sửa model / tham số

Sửa trực tiếp `local_infer/models-preset.ini` (section `[chat]` / `[embed]`), rồi restart.
Key trong INI = tên dài của flag llama-server bỏ `--` (`ctx-size = 32768` ⇔ `--ctx-size 32768`).

Mẹo tiết kiệm RAM: nếu muốn embedding chỉ ở trạng thái sẵn sàng (load khi request đầu tiên),
đặt `load-on-startup = false` ở section `[embed]`.

## 5. Quay lại cách chạy cũ

Không thay đổi gì trong repo — chỉ cần chạy lại 2 lệnh `./llama-server` gốc trên cổng
8080/8081 và đặt `OPENAI_BASE_URL` về cổng tương ứng.
