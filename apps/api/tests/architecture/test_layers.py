"""Kiểm tra kiến trúc phân tầng (Layered Architecture — SDS Hình 1) tự động trong CI.

    presentation ──▶ business ──▶ data_access ──▶ data
          │              │                          ▲
          └──────────────┴──────▶ infrastructure ───┘ (chỉ data.database, data.models.job)

Luật:
 L1  Mỗi tầng chỉ import các tầng được phép (ALLOWED) — không gọi ngược lên, không nhảy tầng.
 L2  Service ở business chỉ dùng service khác qua package `business.<service>` (public API).
 L3  Không có phụ thuộc vòng giữa các service.
 L4  Service chỉ dùng repository mà nó SỞ HỮU (OWNERSHIP) — "phần nào ra phần đấy".
 L5  Business không tự viết SQL (không select/insert/update/delete/text, không dialects).
 L6  Data Access không commit transaction (business quyết định commit).
 L7  Mỗi service có __init__.py khai báo __all__ (public API).
"""

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src" / "quickassist"
LAYERS = ("presentation", "business", "data_access", "data", "infrastructure")

ALLOWED: dict[str, tuple[str, ...]] = {
    "presentation": ("presentation", "business", "infrastructure", "data.database"),
    "business": ("business", "data_access", "data", "infrastructure"),
    "data_access": ("data_access", "data"),
    "data": ("data", "infrastructure.config"),
    "infrastructure": ("infrastructure", "data.database", "data.models.job"),
}

OWNERSHIP: dict[str, set[str]] = {
    "auth": {"user_repository", "auth_session_repository"},
    "notes": {"folder_repository", "note_repository"},
    "quota": {"quota_repository"},
    "semantic_search": {"note_chunk_repository"},
    "summary": set(),
    "rag": set(),
    "common": {"idempotency_repository"},
    "system": {"system_repository"},
}


def _py(layer: str) -> list[Path]:
    return sorted((ROOT / layer).rglob("*.py"))


def _imports(path: Path) -> list[tuple[str, list[str]]]:
    """[(module, [names])] cho mọi import tuyệt đối."""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [(a.name, []) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.append((node.module, [a.name for a in node.names]))
    return out


def _qa_target(mod: str) -> str | None:
    return mod[len("quickassist."):] if mod.startswith("quickassist.") else None


def test_L1_layers_only_depend_downwards() -> None:
    bad = []
    for layer in LAYERS:
        for f in _py(layer):
            for mod, _ in _imports(f):
                t = _qa_target(mod)
                if t and not any(t == a or t.startswith(a + ".") for a in ALLOWED[layer]):
                    bad.append(f"{f.relative_to(ROOT)} -> {mod}")
    assert not bad, "Import sai tầng:\n" + "\n".join(bad)


def _service_of(f: Path) -> str | None:
    rel = f.relative_to(ROOT / "business").parts
    return rel[0] if len(rel) > 1 else None


def test_L2_services_talk_through_public_package() -> None:
    bad = []
    for f in _py("business"):
        own = _service_of(f)
        for mod, _ in _imports(f):
            p = mod.split(".")
            if mod.startswith("quickassist.business.") and len(p) >= 3 and p[2] not in (own, "common"):
                if len(p) != 3:
                    bad.append(f"{f.relative_to(ROOT)} -> {mod} (dùng quickassist.business.{p[2]})")
    assert not bad, "Gọi service khác phải qua package public:\n" + "\n".join(bad)


def test_L3_no_cycles_between_services() -> None:
    graph: dict[str, set[str]] = defaultdict(set)
    for f in _py("business"):
        own = _service_of(f)
        for mod, _ in _imports(f):
            p = mod.split(".")
            is_svc = mod.startswith("quickassist.business.") and len(p) >= 3
            if own and is_svc and p[2] not in (own, "common"):
                graph[own].add(p[2])
    done: set[str] = set()

    def dfs(n: str, path: list[str]) -> None:
        assert n not in path, f"Phụ thuộc vòng: {' -> '.join(path + [n])}"
        if n in done:
            return
        for m in graph[n]:
            dfs(m, path + [n])
        done.add(n)

    for n in list(graph):
        dfs(n, [])


def test_L4_services_use_only_their_own_repositories() -> None:
    bad = []
    for f in _py("business"):
        own = _service_of(f)
        if own is None:
            continue
        for mod, _ in _imports(f):
            if mod.startswith("quickassist.data_access.repositories."):
                repo = mod.split(".")[-1]
                if repo not in OWNERSHIP.get(own, set()):
                    bad.append(f"{f.relative_to(ROOT)} dùng {repo} (thuộc service khác)")
    assert not bad, "Dùng repository không thuộc quyền sở hữu:\n" + "\n".join(bad)


def test_L5_business_does_not_write_sql() -> None:
    sql = {"select", "insert", "update", "delete", "text"}
    bad = []
    for f in _py("business"):
        for mod, names in _imports(f):
            if mod.startswith("sqlalchemy.dialects") or (mod == "sqlalchemy" and sql & set(names)):
                bad.append(f"{f.relative_to(ROOT)} -> {mod} {names}")
    assert not bad, "SQL phải nằm ở data_access:\n" + "\n".join(bad)


def test_L6_data_access_never_commits() -> None:
    bad = [str(f.relative_to(ROOT)) for f in _py("data_access")
           if ".commit(" in f.read_text(encoding="utf-8")]
    assert not bad, f"Repository không được commit: {bad}"


def test_L7_every_service_declares_public_api() -> None:
    for d in sorted(p for p in (ROOT / "business").iterdir() if p.is_dir() and p.name != "__pycache__"):
        if d.name == "common":
            continue
        init = (d / "__init__.py").read_text(encoding="utf-8")
        assert "__all__" in init, f"business/{d.name}/__init__.py phải khai báo __all__"
        assert d.name in OWNERSHIP, f"Thêm business/{d.name} vào OWNERSHIP trong test này"
