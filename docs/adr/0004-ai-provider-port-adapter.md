# ADR-0004: AI qua port/adapter, có mock provider

**Bối cảnh.** SDS chốt OpenAI; báo cáo ý tưởng và kế hoạch nhắc Dify/llama.cpp/vLLM và tự triển khai. Test/CI/demo không được phụ thuộc mạng và tiền API.

**Quyết định.** `infrastructure/openai/base.py` định nghĩa Protocol `embed / complete / stream`. Adapter: `openai_client.py` (HTTP thuần qua httpx — trỏ được sang mọi endpoint tương thích OpenAI bằng `OPENAI_BASE_URL`) và `mock_client.py` (deterministic, bag-of-words). Chọn bằng `AI_PROVIDER`. Mọi lần gọi AI phải bọc `quota.reserve → gọi → commit(usage thật) | release`.

**Phương án đã loại.** Gọi SDK OpenAI trực tiếp trong service (khoá cứng vào 1 nhà cung cấp, không test được offline); Dify làm lớp trung gian bắt buộc (thêm 1 hệ thống phải vận hành, khó kiểm soát quota theo token).

**Hệ quả.** (+) Đổi nhà cung cấp = 1 file; test chạy offline; demo có phương án dự phòng. (−) Không dùng được tính năng riêng của SDK (Batch API, Assistants) nếu không mở rộng port.
