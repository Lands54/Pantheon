from __future__ import annotations

import re
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_SERVICE_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+gods\.([a-z_]+)\.service\s+import|import\s+gods\.([a-z_]+)\.service)\b",
    re.MULTILINE,
)


def _iter_prod_py_files() -> list[Path]:
    files: list[Path] = []
    for folder in ("gods", "api", "cli"):
        base = _ROOT / folder
        if not base.exists():
            continue
        files.extend(p for p in base.rglob("*.py") if p.is_file())
    return files


def _allowed_same_domain_import(rel_path: str, domain: str) -> bool:
    return rel_path.startswith(f"gods/{domain}/")


def test_no_cross_module_direct_service_imports():
    violations: list[str] = []
    for path in _iter_prod_py_files():
        rel = path.relative_to(_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for m in _SERVICE_IMPORT_RE.finditer(text):
            domain = m.group(1) or m.group(2) or ""
            if _allowed_same_domain_import(rel, domain):
                continue
            violations.append(f"{rel}: direct import gods.{domain}.service is forbidden; use gods.{domain}.facade")
    assert not violations, "\n".join(violations)

