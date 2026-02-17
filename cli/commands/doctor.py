"""
CLI Doctor Command - Project repair and readiness checks.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import requests

from cli.utils import get_base_url
from gods.config.models import ProjectConfig
from gods.mnemosyne.policy_registry import ensure_memory_policy, validate_memory_policy


def _load_local_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_local_config(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_project_in_config(cfg: dict, project_id: str, fixes: list[str]) -> dict:
    changed = False
    if not isinstance(cfg, dict):
        cfg = {}
        changed = True
    if not isinstance(cfg.get("projects"), dict):
        cfg["projects"] = {}
        changed = True
    if project_id not in cfg["projects"]:
        cfg["projects"][project_id] = ProjectConfig().model_dump()
        fixes.append(f"新增项目配置: projects.{project_id}")
        changed = True
    if str(cfg.get("current_project", "")).strip() != project_id:
        cfg["current_project"] = project_id
        fixes.append(f"切换 current_project -> {project_id}")
        changed = True
    if changed:
        cfg["_changed"] = True
    return cfg


def _ensure_project_layout(project_id: str, fixes: list[str]):
    root = Path("projects") / project_id
    runtime = root / "runtime"
    mn = root / "mnemosyne"
    required_dirs = [
        root / "agents",
        root / "buffers",
        runtime,
        runtime / "locks",
        mn,
        mn / "agent_profiles",
        mn / "runtime_events",
        mn / "chronicles",
    ]
    for d in required_dirs:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            fixes.append(f"创建目录: {d}")

    for f in [runtime / "events.jsonl", runtime / "detach_jobs.jsonl"]:
        if not f.exists():
            f.write_text("", encoding="utf-8")
            fixes.append(f"创建文件: {f}")


def _ensure_active_agents_minimal(cfg: dict, project_id: str, fixes: list[str]):
    proj = (cfg.get("projects") or {}).get(project_id) or {}
    active_agents = proj.get("active_agents") or []
    for aid in active_agents:
        agent_md = Path("projects") / project_id / "agents" / str(aid) / "agent.md"
        if not agent_md.exists():
            agent_md.parent.mkdir(parents=True, exist_ok=True)
            agent_md.write_text(f"# {aid}\n\n你是 {aid}，请遵守系统契约并完成任务。\n", encoding="utf-8")
            fixes.append(f"补齐 agent 指令文件: {agent_md}")


def _repair_memory_policy(project_id: str, fixes: list[str]):
    path = ensure_memory_policy(project_id)
    raw = {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    changed = False
    fixed_count = 0
    for k, rule in raw.items():
        if not isinstance(rule, dict):
            continue
        if "template" in rule:
            rule.pop("template", None)
            changed = True
            fixed_count += 1
        if "template_chronicle" in rule:
            rule["chronicle_template_key"] = str(rule.pop("template_chronicle") or "")
            changed = True
            fixed_count += 1
        if "template_runtime_log" in rule:
            rule["runtime_log_template_key"] = str(rule.pop("template_runtime_log") or "")
            changed = True
            fixed_count += 1
        if "chronicle_template_key" not in rule:
            rule["chronicle_template_key"] = ""
            changed = True
            fixed_count += 1
        if "runtime_log_template_key" not in rule:
            rule["runtime_log_template_key"] = ""
            changed = True
            fixed_count += 1
        # doctor 自动修复: 开启 chronicle 但无模板 -> 自动降级为仅 runtime_log
        tpl_ch = str(rule.get("chronicle_template_key", "") or "").strip()
        if bool(rule.get("to_chronicle", False)) and not tpl_ch:
            rule["to_chronicle"] = False
            changed = True
            fixed_count += 1
    if changed:
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        fixes.append(f"修复 memory_policy 字段/规则 {fixed_count} 项: {path}")


def _run_guard(script: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    ok = proc.returncode == 0
    output = (proc.stdout or "").strip()
    return ok, output


def _short_output(text: str, max_lines: int = 12) -> str:
    lines = [ln for ln in str(text or "").splitlines() if ln.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def cmd_doctor(args):
    cfg_path = Path("config.json")
    local_cfg = _load_local_config(cfg_path)
    project_id = str(args.project or local_cfg.get("current_project", "default") or "default").strip() or "default"

    fixes: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    checks: list[tuple[str, bool, str]] = []

    local_cfg = _ensure_project_in_config(local_cfg, project_id, fixes)
    _ensure_project_layout(project_id, fixes)
    _ensure_active_agents_minimal(local_cfg, project_id, fixes)
    _repair_memory_policy(project_id, fixes)

    if local_cfg.pop("_changed", False) or fixes:
        _save_local_config(cfg_path, local_cfg)

    # Strict validate after repair
    try:
        out = validate_memory_policy(project_id, ensure_exists=True)
        checks.append(("memory_policy", True, f"required={out.get('required_keys')} validated={out.get('validated_keys')}"))
    except Exception as e:
        checks.append(("memory_policy", False, str(e)))
        blockers.append(f"memory_policy 校验失败: {e}")

    # Optional server health
    base = get_base_url()
    try:
        r = requests.get(f"{base}/health", timeout=2)
        ok = r.status_code == 200
        checks.append(("server_health", ok, f"status={r.status_code}"))
        if not ok:
            warnings.append(f"服务器未就绪: {base}/health -> {r.status_code}")
    except Exception as e:
        checks.append(("server_health", False, str(e)))
        warnings.append(f"服务器不可达: {e}")

    guard_scripts = [
        "scripts/check_import_cycles.py",
        "scripts/check_call_boundaries.py",
        "scripts/check_no_legacy_paths.py",
        "scripts/check_event_bus_integrity.py",
    ]
    if not args.skip_guards:
        for script in guard_scripts:
            ok, output = _run_guard(script)
            checks.append((script, ok, _short_output(output)))
            if not ok:
                if args.strict:
                    blockers.append(f"{script} 失败")
                else:
                    warnings.append(f"{script} 失败（规范告警，不阻断运行）")

    print(f"\n🩺 Doctor Report - project={project_id}\n")
    if fixes:
        print("✅ 自动修复:")
        for x in fixes:
            print(f"  - {x}")
    else:
        print("✅ 自动修复: 无")

    print("\n🔎 检查结果:")
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        print(f"  - [{mark}] {name}")
        if detail:
            for ln in detail.splitlines():
                print(f"      {ln}")

    if warnings:
        print("\n⚠️ 警告:")
        for w in warnings:
            print(f"  - {w}")

    print("\n📌 结论:")
    if blockers:
        print("  - 可运行度: 部分阻塞（需处理下列问题）")
        for b in blockers:
            print(f"  - {b}")
        raise SystemExit(1)
    print("  - 可运行度: 高（核心修复与守门项已通过）")
    raise SystemExit(0)
