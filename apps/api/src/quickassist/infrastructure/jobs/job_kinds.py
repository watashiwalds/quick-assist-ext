"""Danh sách tên job — hợp đồng giao tiếp bất đồng bộ giữa các service ở Business Layer.

Service phát job không cần import service xử lý job → không phụ thuộc vòng.
Thêm job mới: khai báo ở đây + viết handler trong business/<service>/*_job.py
+ nạp file đó trong worker.load_job_handlers().
"""

# Xử lý bởi: business/semantic_search. Payload: {"note_id": str}.
# Phát bởi:  business/notes khi note được tạo/sửa nội dung/chuyển thư mục/xoá.
SEMANTIC_SEARCH_INDEX_NOTE = "semantic_search.index_note"
