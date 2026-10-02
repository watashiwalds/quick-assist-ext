"""Data Access Layer (SDS Hình 1: "RepositoryService") — một repository cho mỗi nhóm bảng.

Repository chỉ chứa truy vấn (SQL/ORM), không chứa nghiệp vụ, không commit.
Ai được dùng repository nào: xem OWNERSHIP trong tests/architecture/test_layers.py.
"""
