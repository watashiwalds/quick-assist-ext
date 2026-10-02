"""Danh sách tên job — hợp đồng giao tiếp bất đồng bộ giữa các module.

Module phát job không cần import module xử lý job → không phụ thuộc vòng.
Thêm job mới: khai báo ở đây + viết handler trong `modules/<owner>/handlers.py`.
"""

# Owner: search. Payload: {"note_id": str}. Phát khi note được tạo/sửa/chuyển thư mục/xoá.
SEARCH_INDEX_NOTE = "search.index_note"
