"""Kiểm tra kiến trúc tự động — chạy trong CI, PR vi phạm sẽ đỏ.

Luật:
1. core/      KHÔNG import modules/ hay providers/   (core là nền, không biết nghiệp vụ)
2. providers/ KHÔNG import modules/                  (adapter không biết nghiệp vụ)
3. modules/A  chỉ được import modules/B qua `quickassist.modules.B.public`
4. Đồ thị phụ thuộc giữa các module KHÔNG có vòng
"""

import ast
from collections import defaultdict
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "quickassist"


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.append(node.module)
    return [m for m in out if m.startswith("quickassist")]


def _files(sub: str) -> list[Path]:
    return sorted((SRC / sub).rglob("*.py"))


def test_core_is_independent() -> None:
    bad = [(f.name, m) for f in _files("core") for m in _imports(f)
           if m.startswith(("quickassist.modules", "quickassist.providers"))]
    assert not bad, f"core không được phụ thuộc modules/providers: {bad}"


def test_providers_do_not_know_business_modules() -> None:
    bad = [(f.name, m) for f in _files("providers") for m in _imports(f)
           if m.startswith("quickassist.modules")]
    assert not bad, f"providers không được import modules: {bad}"


def _module_of(path: Path) -> str:
    return path.relative_to(SRC / "modules").parts[0]


def test_cross_module_imports_only_via_public() -> None:
    bad = []
    for f in _files("modules"):
        own = _module_of(f)
        for m in _imports(f):
            parts = m.split(".")
            if len(parts) >= 3 and parts[1] == "modules" and parts[2] != own:
                if len(parts) < 4 or parts[3] != "public":
                    bad.append(f"{f.relative_to(SRC)} -> {m}")
    assert not bad, "Chỉ được import module khác qua .public:\n" + "\n".join(bad)


def test_no_cycles_between_modules() -> None:
    graph: dict[str, set[str]] = defaultdict(set)
    for f in _files("modules"):
        own = _module_of(f)
        for m in _imports(f):
            parts = m.split(".")
            if len(parts) >= 3 and parts[1] == "modules" and parts[2] != own:
                graph[own].add(parts[2])

    visiting, done = set(), set()

    def dfs(n: str, path: list[str]) -> None:
        if n in done:
            return
        assert n not in visiting, f"Phụ thuộc vòng: {' -> '.join(path + [n])}"
        visiting.add(n)
        for nxt in graph[n]:
            dfs(nxt, path + [n])
        visiting.discard(n)
        done.add(n)

    for node in list(graph):
        dfs(node, [])


def test_every_module_has_standard_layout() -> None:
    for d in sorted(p for p in (SRC / "modules").iterdir() if p.is_dir() and p.name != "__pycache__"):
        names = {p.name for p in d.glob("*.py")}
        assert {"__init__.py", "public.py", "router.py"} <= names, f"{d.name} thiếu file chuẩn: {names}"
