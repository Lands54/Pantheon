from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_checker():
    repo = Path(__file__).resolve().parents[2]
    script = repo / "scripts" / "check_call_boundaries.py"
    spec = importlib.util.spec_from_file_location("check_call_boundaries", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _prepare_repo(tmp_path: Path):
    (tmp_path / "api" / "routes").mkdir(parents=True, exist_ok=True)
    (tmp_path / "api" / "services").mkdir(parents=True, exist_ok=True)
    (tmp_path / "gods").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)


def test_whitebox_same_domain_internal_allowed_with_reason(tmp_path):
    checker = _load_checker()
    _prepare_repo(tmp_path)
    f = tmp_path / "tests" / "whitebox" / "runtime" / "test_ok.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        "# @whitebox-reason: 需要验证 runtime 内部状态迁移\n"
        "from gods.runtime.detach.store import create_job\n",
        encoding="utf-8",
    )
    violations = checker.run_checks(tmp_path)
    assert violations == []


def test_whitebox_requires_reason_header(tmp_path):
    checker = _load_checker()
    _prepare_repo(tmp_path)
    f = tmp_path / "tests" / "whitebox" / "runtime" / "test_no_reason.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("from gods.runtime.detach.store import create_job\n", encoding="utf-8")
    violations = checker.run_checks(tmp_path)
    assert any("whitebox test must include '@whitebox-reason:'" in v.detail for v in violations)


def test_whitebox_cannot_cross_domain_internal(tmp_path):
    checker = _load_checker()
    _prepare_repo(tmp_path)
    f = tmp_path / "tests" / "whitebox" / "runtime" / "test_cross_domain.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        "# @whitebox-reason: 仅验证 runtime 白盒\n"
        "from gods.janus.strategies.structured_v1 import StructuredV1ContextStrategy\n",
        encoding="utf-8",
    )
    violations = checker.run_checks(tmp_path)
    assert any("may not import internal modules of 'janus'" in v.detail for v in violations)
