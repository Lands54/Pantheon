#!/usr/bin/env python3
"""Check architectural call-boundary rules via AST import scanning."""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CORE_DOMAINS = {"angelia", "iris", "hermes", "mnemosyne", "janus", "runtime"}


@dataclass
class Violation:
    rule: str
    file: str
    line: int
    module: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "file": self.file,
            "line": self.line,
            "module": self.module,
            "detail": self.detail,
        }


def _iter_imports(path: Path) -> Iterable[tuple[int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                rows.append((int(getattr(node, "lineno", 1)), str(alias.name)))
        elif isinstance(node, ast.ImportFrom):
            if node.level and not node.module:
                continue
            module = str(node.module or "")
            if module:
                rows.append((int(getattr(node, "lineno", 1)), module))
    return rows


def _is_stdlib_or_external(module: str) -> bool:
    if not module:
        return True
    top = module.split(".")[0]
    if top in {"api", "gods", "tests", "scripts", "cli"}:
        return False
    return True


def _check_routes(path: Path, imports: list[tuple[int, str]], out: list[Violation]):
    for line, mod in imports:
        if mod.startswith("gods"):
            out.append(Violation("R1", str(path), line, mod, "api/routes must not import gods.*"))
            continue
        if mod.startswith("api"):
            if mod == "api.models" or mod.startswith("api.services"):
                continue
            out.append(Violation("R1", str(path), line, mod, "api/routes may only import api.services.* or api.models"))


def _check_services(path: Path, imports: list[tuple[int, str]], out: list[Violation]):
    for line, mod in imports:
        if not mod.startswith("gods."):
            continue
        parts = mod.split(".")
        # gods.<domain> is allowed
        if len(parts) <= 2:
            continue
        # gods.<domain>.facade[.*] is allowed
        if len(parts) >= 3 and parts[2] == "facade":
            continue
        out.append(
            Violation(
                "R2",
                str(path),
                line,
                mod,
                "api/services must use gods.<domain>.facade (or gods.<domain> top-level) only",
            )
        )


def _check_gods_cross_domain(repo: Path, path: Path, imports: list[tuple[int, str]], out: list[Violation]):
    rel = path.relative_to(repo / "gods")
    parts_rel = rel.parts
    if not parts_rel:
        return
    cur_domain = parts_rel[0]
    if cur_domain not in CORE_DOMAINS:
        return
    if path.name in {"facade.py", "contracts.py", "errors.py", "__init__.py"}:
        return

    for line, mod in imports:
        if not mod.startswith("gods."):
            continue
        parts = mod.split(".")
        if len(parts) < 3:
            continue
        other_domain = parts[1]
        if other_domain not in CORE_DOMAINS or other_domain == cur_domain:
            continue
        if parts[2] == "facade":
            continue
        out.append(
            Violation(
                "R3",
                str(path),
                line,
                mod,
                f"cross-domain import from '{cur_domain}' to '{other_domain}' must go through facade",
            )
        )


def _check_tests(path: Path, imports: list[tuple[int, str]], out: list[Violation]):
    whitebox_domain = _whitebox_domain(path)
    if whitebox_domain:
        _check_whitebox_reason(path, out)
    for line, mod in imports:
        if not mod.startswith("gods."):
            continue
        parts = mod.split(".")
        if len(parts) < 3:
            continue
        domain = parts[1]
        if domain not in CORE_DOMAINS:
            continue
        if whitebox_domain:
            # Whitebox tests can access same-domain internals only.
            if domain == whitebox_domain:
                continue
            if parts[2] == "facade":
                continue
            out.append(
                Violation(
                    "R4",
                    str(path),
                    line,
                    mod,
                    f"whitebox test for '{whitebox_domain}' may not import internal modules of '{domain}'",
                )
            )
            continue
        if parts[2] == "facade":
            continue
        out.append(
            Violation(
                "R4",
                str(path),
                line,
                mod,
                "tests for core domains must import through facade only",
            )
        )


def _whitebox_domain(path: Path) -> str | None:
    parts = path.parts
    try:
        idx = parts.index("whitebox")
    except ValueError:
        return None
    if idx + 1 >= len(parts):
        return None
    domain = parts[idx + 1]
    return domain if domain in CORE_DOMAINS else None


def _check_whitebox_reason(path: Path, out: list[Violation]):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return
    header = "\n".join(text.splitlines()[:40]).lower()
    if "@whitebox-reason:" in header:
        return
    out.append(
        Violation(
            "R4",
            str(path),
            1,
            "(file-header)",
            "whitebox test must include '@whitebox-reason:' comment in file header",
        )
    )


def run_checks(repo: Path) -> list[Violation]:
    violations: list[Violation] = []

    for path in (repo / "api" / "routes").glob("*.py"):
        if path.name == "__init__.py":
            continue
        imports = list(_iter_imports(path))
        _check_routes(path, imports, violations)

    for path in (repo / "api" / "services").rglob("*.py"):
        if path.name == "__init__.py":
            continue
        imports = list(_iter_imports(path))
        _check_services(path, imports, violations)

    for path in (repo / "gods").rglob("*.py"):
        imports = list(_iter_imports(path))
        _check_gods_cross_domain(repo, path, imports, violations)

    for path in (repo / "tests").rglob("*.py"):
        imports = list(_iter_imports(path))
        _check_tests(path, imports, violations)

    # R5: hard bans for interaction-only boundaries
    for path in (repo / "gods" / "hermes").rglob("*.py"):
        imports = list(_iter_imports(path))
        for line, mod in imports:
            if mod.startswith("gods.iris.facade"):
                violations.append(
                    Violation(
                        "R5",
                        str(path),
                        line,
                        mod,
                        "gods/hermes must not import gods.iris.facade directly; use interaction events",
                    )
                )
    comm_human = repo / "gods" / "tools" / "comm_human.py"
    if comm_human.exists():
        for line, mod in _iter_imports(comm_human):
            if mod.startswith("gods.iris"):
                violations.append(
                    Violation(
                        "R5",
                        str(comm_human),
                        line,
                        mod,
                        "tools/comm_human must not call iris directly; submit interaction events",
                    )
                )

    return violations


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    violations = run_checks(repo)
    payload = {
        "violation_count": len(violations),
        "violations": [v.to_dict() for v in violations],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if violations:
        print(f"CALL_BOUNDARY_VIOLATION_COUNT {len(violations)}")
        return 1
    print("CALL_BOUNDARY_VIOLATION_COUNT 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
