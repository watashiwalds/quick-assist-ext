# ADR-0001: Layered Architecture trong một modular monolith

**Bối cảnh.** SDS Hình 1 vẽ kiến trúc phân tầng: Presentation & Integration → Business & Application → Data Access → Data, cùng Infrastructure Layer. Tuy nhiên §5.2 lại viết "phân tách thành các microservice độc lập", trong khi §4.2 nói API và worker chạy cùng máy. Nhóm có 4 người, làm trong 8 tuần, tải demo nhỏ. Thứ cần nhất là chia việc rõ ràng và không mất dữ liệu.

**Quyết định.**
1. **Kiến trúc phân tầng đúng Hình 1**, mỗi tầng một thư mục: `presentation/`, `business/`, `data_access/`, `data/`, `infrastructure/`. Phụ thuộc chỉ đi xuống (luật L1–L7, có test tự động).
2. **Trong Business Layer, mỗi service của SDS là một thư mục** (`auth, notes, quota, semantic_search, summary, rag`). Service khác chỉ được gọi qua package (public API). Service chỉ dùng repository của bảng mà nó sở hữu.
3. **Triển khai dạng monolith gồm 2 tiến trình**: `api` (`main.py`) và `worker` (`worker.py`), dùng chung codebase và một CSDL.

**Phương án đã loại.**
| Phương án | Lý do loại |
|---|---|
| Microservice (5 service + gateway) | Phải lo 5 deploy, service discovery, độ trễ mạng, và transaction phân tán khi xoá tài khoản. Chi phí này vượt xa lợi ích ở quy mô môn học. |
| Chia theo feature, không tách tầng (`modules/notes/{router,service,repository}.py`) | Không thấy được các tầng của SDS, khó đối chiếu khi chấm SDS. Repository chung dễ bị dùng lẫn. |
| Phân tầng nhưng không chia service bên trong | 4 người cùng sửa một file `services.py`, không phân công được theo SDS. |

**Hệ quả.**
- (+) Cấu trúc thư mục khớp 1–1 với SDS Hình 1 và §5.2 (bảng đối chiếu ở `docs/architecture/README.md` §4).
- (+) Xoá tài khoản chạy trong một transaction ACID. Gọi giữa các service là function call. Chỉ cần một lần deploy.
- (+) Muốn tách `semantic_search` thành service mạng sau này thì chỉ cần thay package public bằng HTTP client.
- (−) Một tính năng trải qua 4–5 thư mục (controller, service, repository, model). Đó là cái giá của phân tầng; bù lại bằng việc đặt tên file nhất quán theo service.
- (−) Không scale riêng từng service được. Chấp nhận, vì API stateless và worker vẫn scale ngang được.
