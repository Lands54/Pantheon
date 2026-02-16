#!/usr/bin/env python3
"""Detect import cycles inside a Python package tree."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Iterable


def _module_name(root: Path, py_file: Path) -> str:
    rel = py_file.relative_to(root.parent).with_suffix("")
    return ".".join(rel.parts)


def _discover_modules(pkg_root: Path) -> dict[str, Path]:
    return {_module_name(pkg_root, p): p for p in pkg_root.rglob("*.py")}


def _resolve_from_import(cur_mod: str, level: int, module: str | None) -> str:
    parts = cur_mod.split(".")[:-1]
    if level > 0:
        up = max(0, len(parts) - (level - 1))
        parts = parts[:up]
    if module:
        parts = parts + module.split(".")
    return ".".join(parts)


def _edges(modules: dict[str, Path]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {m: set() for m in modules}
    for mod, path in modules.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name in modules:
                        out[mod].add(name)
            elif isinstance(node, ast.ImportFrom):
                target = _resolve_from_import(mod, node.level, node.module)
                if target in modules:
                    out[mod].add(target)
    return out


def _dedupe_cycles(cycles: Iterable[list[str]]) -> list[list[str]]:
    seen: set[tuple[str, ...]] = set()
    uniq: list[list[str]] = []
    for cyc in cycles:
        body = cyc[:-1]
        if not body:
            continue
        rots = [tuple(body[i:] + body[:i]) for i in range(len(body))]
        key = min(rots)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(cyc)
    return uniq


def find_cycles(pkg_root: Path) -> list[list[str]]:
    modules = _discover_modules(pkg_root)
    graph = _edges(modules)
    visited: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def dfs(u: str):
        visited[u] = 1
        stack.append(u)
        for v in graph.get(u, set()):
            if v not in visited:
                dfs(v)
            elif visited[v] == 1:
                i = stack.index(v)
                cycles.append(stack[i:] + [v])
        stack.pop()
        visited[u] = 2

    for m in graph:
        if m not in visited:
            dfs(m)

    return _dedupe_cycles(cycles)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check import cycles in package")
    parser.add_argument("--root", default="gods", help="Package root directory")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args()

    root = Path(args.root)
    cycles = find_cycles(root)

    if args.json:
        print(json.dumps({"root": str(root), "cycle_count": len(cycles), "cycles": cycles}, ensure_ascii=False, indent=2))
    else:
        print(f"CYCLE_COUNT {len(cycles)}")
        for c in cycles:
            print(" -> ".join(c))

    return 0 if not cycles else 1


if __name__ == "__main__":
    raise SystemExit(main())
