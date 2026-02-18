from __future__ import annotations

import json
import os
import random
import re
import signal
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import threading

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from gods.iris.facade import enqueue_message
from gods.mnemosyne import write_entry
from gods.angelia.facade import inject_inbox_before_pulse
from gods.runtime.facade import detach_submit


def _mk_project(round_idx: int) -> tuple[str, str]:
    project_id = f"it_cognitive_bench_{round_idx}_{uuid.uuid4().hex[:6]}"
    agent_id = "bench"
    peer_id = "peer"

    (Path("projects") / project_id / "agents" / agent_id).mkdir(parents=True, exist_ok=True)
    (Path("projects") / project_id / "agents" / peer_id).mkdir(parents=True, exist_ok=True)
    prof = Path("projects") / project_id / "mnemosyne" / "agent_profiles"
    prof.mkdir(parents=True, exist_ok=True)
    (prof / f"{agent_id}.md").write_text("# bench\n执行认知基准测试。", encoding="utf-8")
    (prof / f"{peer_id}.md").write_text("# peer\n被动接收消息。", encoding="utf-8")
    return project_id, agent_id


def _setup_config(project_id: str, agent_id: str):
    old = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="it cognitive benchmark",
        active_agents=[agent_id, "peer"],
        agent_settings={
            agent_id: AgentModelConfig(disabled_tools=[]),
            "peer": AgentModelConfig(disabled_tools=[]),
        },
        simulation_enabled=False,
        phase_strategy="freeform",
        tool_loop_max=8,
        context_strategy="structured_v1",
        context_budget_state_window=18000,
        context_state_window_limit=80,
    )
    return old


def _cleanup(project_id: str, old_project):
    if old_project is None:
        runtime_config.projects.pop(project_id, None)
    else:
        runtime_config.projects[project_id] = old_project
    shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def _read_observations(project_id: str, agent_id: str) -> list[dict]:
    p = Path("projects") / project_id / "mnemosyne" / "observations" / f"{agent_id}.jsonl"
    if not p.exists():
        return []
    rows: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _tool_metrics(rows: list[dict]) -> dict:
    tracked = {"list", "send_message", "check_outbox"}
    filtered = [r for r in rows if str(r.get("tool", "")) in tracked]
    total = len(filtered)
    ok = sum(1 for r in filtered if str(r.get("status", "")) == "ok")
    return {
        "total_calls": total,
        "ok_calls": ok,
        "accuracy": (ok / total) if total else 0.0,
    }


def _run_agent_once(agent: GodAgent, state: dict) -> tuple[dict, str]:
    out = agent.process(state)
    last = state.get("messages", [])[-1] if state.get("messages") else None
    content = str(getattr(last, "content", "") if last is not None else "")
    return out, content


def _run_agent_once_with_timeout(agent: GodAgent, state: dict, timeout_sec: int = 35) -> tuple[dict, str, bool]:
    if threading.current_thread() is not threading.main_thread():
        # SIGALRM 仅支持主线程；并发 round（线程池）下退化为直接执行。
        out, content = _run_agent_once(agent, state)
        return out, content, False

    class _Alarm(Exception):
        pass

    def _handler(signum, frame):
        raise _Alarm()

    old_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(max(1, int(timeout_sec)))
    try:
        out, content = _run_agent_once(agent, state)
        return out, content, False
    except _Alarm:
        state["next_step"] = "continue"
        return state, "LIVE_TIMEOUT", True
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class _ToolFlowBrain:
    def __init__(self):
        self.turn = 0
        self.system_prompts: list[str] = []

    def think_with_tools(self, messages, tools, trace_meta=None):
        self.system_prompts.append(str(getattr(messages[0], "content", "") if messages else ""))
        script = [
            AIMessage(content="check dir", tool_calls=[{"id": "t1", "name": "list", "args": {"path": "."}}]),
            AIMessage(
                content="reply sender",
                tool_calls=[
                    {
                        "id": "t2",
                        "name": "send_message",
                        "args": {"to_id": "peer", "title": "ack", "message": "收到，开始执行。"},
                    }
                ],
            ),
            AIMessage(content="check receipt", tool_calls=[{"id": "t3", "name": "check_outbox", "args": {"limit": 20}}]),
            AIMessage(content="done", tool_calls=[]),
        ]
        idx = min(self.turn, len(script) - 1)
        self.turn += 1
        return script[idx]


class _MemoryRecallBrain:
    def __init__(self):
        self.turn = 0

    def think_with_tools(self, messages, tools, trace_meta=None):
        sys_text = str(getattr(messages[0], "content", "") if messages else "")
        if self.turn == 0:
            self.turn += 1
            return AIMessage(content="我会记住代号 ORBIT-741", tool_calls=[])
        self.turn += 1
        return AIMessage(
            content=("MEM_OK ORBIT-741" if "ORBIT-741" in sys_text else "MEM_FAIL"),
            tool_calls=[],
        )


class _RestateBrain:
    def think_with_tools(self, messages, tools, trace_meta=None):
        sys_text = str(getattr(messages[0], "content", "") if messages else "")
        key_a = "北门" if "北门" in sys_text else ""
        key_b = "09:30" if "09:30" in sys_text else ""
        text = f"RESTATE {key_a} {key_b}".strip()
        return AIMessage(content=text, tool_calls=[])


class _AssocBrain:
    def __init__(self):
        self.turn = 0

    def think_with_tools(self, messages, tools, trace_meta=None):
        sys_text = str(getattr(messages[0], "content", "") if messages else "")
        if self.turn == 0:
            self.turn += 1
            return AIMessage(content="已记录映射 Astra->Blue, Boreal->Green", tool_calls=[])
        self.turn += 1
        return AIMessage(content=("ASSOC_OK Green" if "Boreal->Green" in sys_text else "ASSOC_FAIL"), tool_calls=[])


def _is_dyck2(seq: str) -> bool:
    stack: list[str] = []
    pairs = {")": "(", "]": "["}
    for ch in seq:
        if ch in "([":
            stack.append(ch)
            continue
        if ch in ")]":
            if not stack or stack[-1] != pairs[ch]:
                return False
            stack.pop()
    return not stack


class _DyckBrain:
    def think_with_tools(self, messages, tools, trace_meta=None):
        sys_text = str(getattr(messages[0], "content", "") if messages else "")
        ms = re.findall(r"DYCK2:\s*([()\[\]]+)", sys_text)
        seq = ms[-1] if ms else ""
        return AIMessage(content=("DYCK_OK" if _is_dyck2(seq) else "DYCK_BAD"), tool_calls=[])


def _state(project_id: str, text: str) -> dict:
    return {
        "project_id": project_id,
        "messages": [HumanMessage(content=text, name="tester")],
        "context": "cognitive benchmark",
        "next_step": "",
    }


def _run_one_round(round_idx: int) -> dict:
    project_id, agent_id = _mk_project(round_idx)
    old = _setup_config(project_id, agent_id)
    result = {
        "round": round_idx,
        "project_id": project_id,
        "tool_flow_pass": False,
        "memory_pass": False,
        "restate_pass": False,
        "assoc_pass": False,
        "dyck_pass_rate": 0.0,
        "tool_metrics": {"total_calls": 0, "ok_calls": 0, "accuracy": 0.0},
    }
    try:
        # 1) Tool-flow: inbox -> reply -> outbox check
        enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="tester",
            title="bootstrap",
            content="请先确认目录，然后回信。",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        s1 = _state(project_id, "开始执行工具流")
        inject_inbox_before_pulse(s1, project_id=project_id, agent_id=agent_id)
        a1 = GodAgent(agent_id=agent_id, project_id=project_id)
        brain1 = _ToolFlowBrain()
        a1.brain = brain1
        out1, _ = _run_agent_once(a1, s1)
        obs = _read_observations(project_id, agent_id)
        tm = _tool_metrics(obs)
        result["tool_metrics"] = tm
        result["tool_flow_pass"] = bool(
            out1.get("next_step") == "finish"
            and tm["total_calls"] >= 3
            and tm["accuracy"] >= 0.66
            and brain1.system_prompts
            and "bootstrap" in brain1.system_prompts[0]
        )

        # 2) Memory recall across pulses
        a2 = GodAgent(agent_id=agent_id, project_id=project_id)
        brain2 = _MemoryRecallBrain()
        a2.brain = brain2
        _run_agent_once(a2, _state(project_id, "请记住代号 ORBIT-741"))
        _, mem_answer = _run_agent_once(a2, _state(project_id, "请复述刚才代号"))
        result["memory_pass"] = "MEM_OK ORBIT-741" in mem_answer

        # 3) Restatement from inbox context
        enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="tester",
            title="brief",
            content="请在09:30前到北门集合，并带上日志。",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        s3 = _state(project_id, "请复述来信")
        inject_inbox_before_pulse(s3, project_id=project_id, agent_id=agent_id)
        a3 = GodAgent(agent_id=agent_id, project_id=project_id)
        a3.brain = _RestateBrain()
        _, restate_answer = _run_agent_once(a3, s3)
        result["restate_pass"] = ("北门" in restate_answer) and ("09:30" in restate_answer)

        # 4) Associative recall
        a4 = GodAgent(agent_id=agent_id, project_id=project_id)
        brain4 = _AssocBrain()
        a4.brain = brain4
        _run_agent_once(a4, _state(project_id, "建立映射: Astra->Blue, Boreal->Green"))
        _, assoc_answer = _run_agent_once(a4, _state(project_id, "问题: Boreal 对应什么颜色?"))
        result["assoc_pass"] = "ASSOC_OK Green" in assoc_answer

        # 5) Dyck-2
        dyck_cases = [
            ("([[]])", True),
            ("([][])", True),
            ("([)]", False),
            ("(()[]][)", False),
        ]
        dyck_ok = 0
        a5 = GodAgent(agent_id=agent_id, project_id=project_id)
        a5.brain = _DyckBrain()
        for seq, expect in dyck_cases:
            _, ans = _run_agent_once(a5, _state(project_id, f"DYCK2: {seq}"))
            got = "DYCK_OK" in ans
            if got == expect:
                dyck_ok += 1
        result["dyck_pass_rate"] = dyck_ok / len(dyck_cases)
        return result
    finally:
        _cleanup(project_id, old)


def _run_one_round_live(round_idx: int) -> dict:
    project_id, agent_id = _mk_project(round_idx)
    old = _setup_config(project_id, agent_id)
    result = {
        "round": round_idx,
        "project_id": project_id,
        "live_mode": True,
        "tool_flow_pass": False,
        "memory_pass": False,
        "restate_pass": False,
        "assoc_pass": False,
        "dyck_pass_rate": 0.0,
        "tool_metrics": {"total_calls": 0, "ok_calls": 0, "accuracy": 0.0},
        "timeouts": 0,
    }
    try:
        # 1) Tool-flow: inbox -> reply -> outbox check
        enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="tester",
            title="bootstrap",
            content=(
                "你必须按顺序执行3步："
                "1) list(path='.')；"
                "2) send_message(to_id='peer', title='ack', message='收到，开始执行。')；"
                "3) check_outbox(limit=20)；"
                "然后输出 done。"
            ),
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        s1 = _state(project_id, "严格按bootstrap消息中的3步工具执行")
        inject_inbox_before_pulse(s1, project_id=project_id, agent_id=agent_id)
        a1 = GodAgent(agent_id=agent_id, project_id=project_id)
        out1, _, to1 = _run_agent_once_with_timeout(a1, s1, timeout_sec=30)
        result["timeouts"] += int(to1)
        obs = _read_observations(project_id, agent_id)
        tm = _tool_metrics(obs)
        result["tool_metrics"] = tm
        result["tool_flow_pass"] = bool(out1.get("next_step") in {"finish", "continue"} and tm["total_calls"] >= 2)

        # 2) Memory recall across pulses
        a2 = GodAgent(agent_id=agent_id, project_id=project_id)
        _, _, to2a = _run_agent_once_with_timeout(a2, _state(project_id, "记住这个代号：ORBIT-741。只回复OK"), timeout_sec=30)
        _, mem_answer, to2b = _run_agent_once_with_timeout(a2, _state(project_id, "只回复刚才代号本体，不要其他字"), timeout_sec=30)
        result["timeouts"] += int(to2a) + int(to2b)
        result["memory_pass"] = "ORBIT-741" in mem_answer

        # 3) Restatement from inbox context
        enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="tester",
            title="brief",
            content="请在09:30前到北门集合，并带上日志。",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        s3 = _state(project_id, "复述brief中时间和地点，只回复: 时间 地点")
        inject_inbox_before_pulse(s3, project_id=project_id, agent_id=agent_id)
        a3 = GodAgent(agent_id=agent_id, project_id=project_id)
        _, restate_answer, to3 = _run_agent_once_with_timeout(a3, s3, timeout_sec=30)
        result["timeouts"] += int(to3)
        result["restate_pass"] = ("北门" in restate_answer) and ("09:30" in restate_answer)

        # 4) Associative recall
        a4 = GodAgent(agent_id=agent_id, project_id=project_id)
        _, _, to4a = _run_agent_once_with_timeout(a4, _state(project_id, "记忆映射：Astra->Blue, Boreal->Green。只回复OK"), timeout_sec=30)
        _, assoc_answer, to4b = _run_agent_once_with_timeout(a4, _state(project_id, "问题：Boreal对应的颜色是什么？只回答颜色"), timeout_sec=30)
        result["timeouts"] += int(to4a) + int(to4b)
        result["assoc_pass"] = "green" in assoc_answer.lower()

        # 5) Dyck-2
        dyck_cases = [
            ("([[]])", True),
            ("([)]", False),
        ]
        dyck_ok = 0
        a5 = GodAgent(agent_id=agent_id, project_id=project_id)
        for seq, expect in dyck_cases:
            _, ans, to5 = _run_agent_once_with_timeout(
                a5,
                _state(project_id, f"判断DYCK2括号串是否合法，只回复 OK 或 BAD。串: {seq}"),
                timeout_sec=30,
            )
            result["timeouts"] += int(to5)
            low = ans.lower()
            got = ("ok" in low) and ("bad" not in low)
            if got == expect:
                dyck_ok += 1
        result["dyck_pass_rate"] = dyck_ok / len(dyck_cases)
        return result
    finally:
        _cleanup(project_id, old)


def _write_report(rounds: int, rows: list[dict]) -> Path:
    overall = {
        "rounds": rounds,
        "avg_tool_accuracy": sum(float(r["tool_metrics"]["accuracy"]) for r in rows) / max(1, len(rows)),
        "memory_pass_rate": sum(1 for r in rows if r["memory_pass"]) / max(1, len(rows)),
        "restate_pass_rate": sum(1 for r in rows if r["restate_pass"]) / max(1, len(rows)),
        "assoc_pass_rate": sum(1 for r in rows if r["assoc_pass"]) / max(1, len(rows)),
        "avg_dyck_pass_rate": sum(float(r["dyck_pass_rate"]) for r in rows) / max(1, len(rows)),
        "tool_flow_pass_rate": sum(1 for r in rows if r["tool_flow_pass"]) / max(1, len(rows)),
    }
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rounds": rounds,
        "overall": overall,
        "per_round": rows,
    }
    out = Path("reports")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "agent_cognitive_benchmark_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_live_report(rounds: int, rows: list[dict]) -> Path:
    overall = {
        "rounds": rounds,
        "avg_tool_accuracy": sum(float(r["tool_metrics"]["accuracy"]) for r in rows) / max(1, len(rows)),
        "memory_pass_rate": sum(1 for r in rows if r["memory_pass"]) / max(1, len(rows)),
        "restate_pass_rate": sum(1 for r in rows if r["restate_pass"]) / max(1, len(rows)),
        "assoc_pass_rate": sum(1 for r in rows if r["assoc_pass"]) / max(1, len(rows)),
        "avg_dyck_pass_rate": sum(float(r["dyck_pass_rate"]) for r in rows) / max(1, len(rows)),
        "tool_flow_pass_rate": sum(1 for r in rows if r["tool_flow_pass"]) / max(1, len(rows)),
    }
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "live_llm",
        "rounds": rounds,
        "overall": overall,
        "per_round": rows,
    }
    out = Path("reports")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "agent_cognitive_benchmark_live_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _minimal_contract_json(agent_id: str) -> str:
    contract = {
        "title": "Bench Contract",
        "version": "1.0.0",
        "description": "strict benchmark contract",
        "submitter": agent_id,
        "committers": [agent_id],
        "status": "active",
        "default_obligations": [
            {
                "id": "health_check",
                "summary": "basic health check",
                "provider": {"type": "http", "url": "http://127.0.0.1:18080/health", "method": "GET"},
                "io": {"request_schema": {"type": "object"}, "response_schema": {"type": "object"}},
                "runtime": {"mode": "sync", "timeout_sec": 5},
            }
        ],
        "obligations": {agent_id: []},
    }
    return json.dumps(contract, ensure_ascii=False)


def _prepare_tool_prompt(project_id: str, agent_id: str, tool_name: str) -> str:
    base = f"你必须只调用一次工具 `{tool_name}`，不得调用其他工具。调用后结束本轮。"
    prompts = {
        "check_inbox": base + " 参数: {}。",
        "check_outbox": base + " 参数: {limit:20}。",
        "send_message": base + " 参数: {to_id:'peer', title:'tool-bench', message:'ping'}。",
        "finalize": base + " 参数: {mode:'done'}。",
        "post_to_synod": base + " 参数: {reason:'bench', message:'sync'}。",
        "abstain_from_synod": base + " 参数: {reason:'bench'}。",
        "list_agents": base + " 参数: {}。",
        "read": base + " 参数: {path:'bench.txt'}。",
        "write_file": base + " 参数: {path:'bench.txt', content:'hello bench'}。",
        "replace_content": base + " 参数: {path:'bench.txt', old:'hello', new:'HELLO'}。",
        "insert_content": base + " 参数: {path:'bench.txt', anchor:'HELLO', content:'\\nINSERTED'}。",
        "multi_replace": base + " 参数: {path:'bench.txt', replacements:[['HELLO','hello']]}。",
        "list": base + " 参数: {path:'.'}。",
        "validate_path": base + " 参数: {path:'bench.txt'}。",
        "run_command": base + " 参数: {command:'python -c \"print(123)\"'}。",
        "run_command_detach": base + " 参数: {command:'python sleeper.py'}。",
        "detach_list": base + " 参数: {limit:20}。",
        "detach_stop": base + " 参数: {job_id:'__JOB_ID__'}。",
        "call_protocol": base + " 参数: {name:'health_check', payload_json:'{}', mode:'sync'}。",
        "route_protocol": base + " 参数: {target_agent:'bench', function_id:'health_check', payload_json:'{}', mode:'sync'}。",
        "check_protocol_job": base + " 参数: {job_id:'bench-missing-job'}。",
        "register_contract": base + " 参数: {contract_json:'__CONTRACT_JSON__'}。",
        "commit_contract": base + " 参数: {title:'Bench Contract', version:'1.0.0'}。",
        "list_contracts": base + " 参数: {}。",
        "disable_contract": base + " 参数: {title:'Bench Contract', version:'1.0.0', reason:'bench'}。",
        "reserve_port": base + " 参数: {owner_id:'bench', preferred_port:18091, note:'bench'}。",
        "release_port": base + " 参数: {owner_id:'bench', port:18091}。",
        "list_port_leases": base + " 参数: {}。",
        "mnemo_write_agent": base + " 参数: {title:'bench-note', content:'note', tags_json:'[\"bench\"]'}。",
        "mnemo_list_agent": base + " 参数: {limit:10}。",
        "mnemo_read_agent": base + " 参数: {entry_id:'__ENTRY_ID__'}。",
    }
    text = prompts.get(tool_name, base + " 参数请使用最小合法参数。")
    text = text.replace("__CONTRACT_JSON__", _minimal_contract_json(agent_id).replace('"', '\\"'))
    return text


def _prepare_tool_preconditions(project_id: str, agent_id: str, tool_name: str) -> dict:
    # Make tool-level preconditions deterministic to maximize one-pass coverage.
    if tool_name in {"read", "replace_content", "insert_content", "multi_replace"}:
        p = Path("projects") / project_id / "agents" / agent_id / "bench.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text("hello bench", encoding="utf-8")
    if tool_name == "check_inbox":
        enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="tester",
            title="inbox-bench",
            content="ping inbox",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
    if tool_name == "check_outbox":
        enqueue_message(
            project_id=project_id,
            agent_id="peer",
            sender=agent_id,
            title="outbox-bench",
            content="ping outbox",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
    if tool_name in {"run_command_detach", "detach_stop"}:
        p = Path("projects") / project_id / "agents" / agent_id / "sleeper.py"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("import time\nfor _ in range(60):\n    time.sleep(1)\n", encoding="utf-8")
    if tool_name == "detach_stop":
        job = detach_submit(project_id=project_id, agent_id=agent_id, command="python sleeper.py")
        return {"job_id": str(job.get("job_id", ""))}
    if tool_name in {"commit_contract", "list_contracts", "disable_contract"}:
        from gods.hermes.facade import hermes_service

        try:
            hermes_service.contracts.register(project_id, json.loads(_minimal_contract_json(agent_id)))
        except Exception:
            pass
    if tool_name == "mnemo_read_agent":
        row = write_entry(project_id, "agent", agent_id, "bench-entry", "hello", ["bench"])
        return {"entry_id": str(row.get("id", ""))}
    return {}


def _run_tool_coverage_suite_live(project_id: str, agent_id: str, timeout_sec: int = 30) -> dict:
    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    tool_names = [t.name for t in agent.get_tools()]
    rows = _read_observations(project_id, agent_id)
    called_ok: dict[str, bool] = {x: False for x in tool_names}
    called_any: dict[str, bool] = {x: False for x in tool_names}
    attempts: dict[str, int] = {x: 0 for x in tool_names}
    timeouts = 0
    max_attempts = max(3, int(os.getenv("AGENT_BENCH_TOOL_ATTEMPTS", "5")))

    for tool in tool_names:
        for _ in range(max_attempts):
            attempts[tool] += 1
            base_len = len(rows)
            meta = _prepare_tool_preconditions(project_id, agent_id, tool)
            prompt = _prepare_tool_prompt(project_id, agent_id, tool)
            if meta.get("job_id"):
                prompt = prompt.replace("__JOB_ID__", str(meta["job_id"]))
            if meta.get("entry_id"):
                prompt = prompt.replace("__ENTRY_ID__", str(meta["entry_id"]))

            state = _state(project_id, prompt)
            if tool == "check_inbox":
                inject_inbox_before_pulse(state, project_id=project_id, agent_id=agent_id)
            _, _, to = _run_agent_once_with_timeout(agent, state, timeout_sec=timeout_sec)
            timeouts += int(to)
            rows = _read_observations(project_id, agent_id)
            delta = rows[base_len:]
            hits = [r for r in delta if str(r.get("tool", "")) == tool]
            if hits:
                called_any[tool] = True
                if any(str(h.get("status", "")) == "ok" for h in hits):
                    called_ok[tool] = True
                break

    return {
        "tool_count": len(tool_names),
        "tool_names": tool_names,
        "called_any_count": sum(1 for k in tool_names if called_any.get(k)),
        "called_ok_count": sum(1 for k in tool_names if called_ok.get(k)),
        "called_any_rate": (sum(1 for k in tool_names if called_any.get(k)) / max(1, len(tool_names))),
        "called_ok_rate": (sum(1 for k in tool_names if called_ok.get(k)) / max(1, len(tool_names))),
        "missing_any": [k for k in tool_names if not called_any.get(k)],
        "missing_ok": [k for k in tool_names if not called_ok.get(k)],
        "attempts": attempts,
        "timeouts": timeouts,
    }


def _extract_first_int(text: str) -> int | None:
    m = re.search(r"-?\d+", str(text or ""))
    return int(m.group(0)) if m else None


def _run_memory_300_suite_live(project_id: str, agent_id: str, rng: random.Random, timeout_sec: int = 30) -> dict:
    nums = [rng.randint(0, 999) for _ in range(300)]
    serialized = ",".join(str(x) for x in nums)
    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    _, _, t0 = _run_agent_once_with_timeout(
        agent,
        _state(project_id, f"记住这个长度300的数字序列，后续会提问第k个数字：{serialized}"),
        timeout_sec=timeout_sec,
    )
    ok = 0
    cases = []
    ks = [5, 17, 33, 57, 89, 123, 167, 211, 257, 300]
    for i in range(10):
        k = ks[i]
        # 每轮插入干扰，检验跨 pulse 保持能力。
        if i > 0:
            _, _, _ = _run_agent_once_with_timeout(
                agent,
                _state(project_id, f"干扰信息{i}: 这条是噪声，不需要记忆。"),
                timeout_sec=timeout_sec,
            )
        _, ans, to = _run_agent_once_with_timeout(
            agent,
            _state(project_id, f"问题{i+1}/10（难度递增）：只回答这个序列的第{k}个数字（1-based），仅输出数字。"),
            timeout_sec=timeout_sec,
        )
        pred = _extract_first_int(ans)
        gold = nums[k - 1]
        passed = pred == gold
        ok += int(passed)
        cases.append({"idx": i + 1, "k": k, "pred": pred, "gold": gold, "pass": passed, "timeout": bool(to)})
    return {
        "cases": cases,
        "pass_count": ok,
        "pass_rate": ok / 10.0,
        "timeouts": int(t0) + sum(1 for c in cases if c["timeout"]),
        "ks": ks,
    }


def _run_restate_suite_live(project_id: str, agent_id: str, timeout_sec: int = 30) -> dict:
    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    ok = 0
    cases = []
    for i in range(10):
        place = f"北门-{i+1}"
        backup_place = f"东门-{i+1}"
        minute = 10 + i * 2
        t = f"{9 + i // 4:02d}:{(25 + minute) % 60:02d}"
        backup_t = f"{10 + i // 3:02d}:{(40 + minute) % 60:02d}"
        content = (
            f"任务{i+1}: 主集合点 {place}，主时间 {t}；"
            f"备选集合点 {backup_place}，备选时间 {backup_t}。"
            "优先使用主集合点和主时间。"
        )
        enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="tester",
            title=f"brief-{i+1}",
            content=content,
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        s = _state(project_id, f"复述第{i+1}条brief主方案的时间和地点，仅输出: 时间 地点")
        inject_inbox_before_pulse(s, project_id=project_id, agent_id=agent_id)
        _, ans, to = _run_agent_once_with_timeout(agent, s, timeout_sec=timeout_sec)
        passed = (place in ans) and (t in ans)
        ok += int(passed)
        cases.append({"idx": i + 1, "time": t, "place": place, "ans": ans[:160], "pass": passed, "timeout": bool(to)})
    return {"cases": cases, "pass_count": ok, "pass_rate": ok / 10.0, "timeouts": sum(1 for c in cases if c["timeout"])}


def _run_assoc_suite_live(project_id: str, agent_id: str, timeout_sec: int = 30) -> dict:
    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    ok = 0
    cases = []
    for i in range(10):
        pairs = [(f"K{j}", f"V{j+i}") for j in range(1, i + 6)]
        mapping_text = ", ".join([f"{k}->{v}" for k, v in pairs])
        target_k, target_v = pairs[-(1 + (i % 3))]
        _, _, to1 = _run_agent_once_with_timeout(
            agent,
            _state(project_id, f"记忆映射集合{i+1}（规模={len(pairs)}）: {mapping_text}。只回复OK"),
            timeout_sec=timeout_sec,
        )
        _, ans, to2 = _run_agent_once_with_timeout(
            agent,
            _state(project_id, f"问题{i+1}/10（难度递增）：{target_k}对应什么？只回复值。"),
            timeout_sec=timeout_sec,
        )
        passed = target_v.lower() in ans.lower()
        ok += int(passed)
        cases.append(
            {
                "idx": i + 1,
                "pairs": len(pairs),
                "k": target_k,
                "gold": target_v,
                "ans": ans[:120],
                "pass": passed,
                "timeout": bool(to1 or to2),
            }
        )
    return {"cases": cases, "pass_count": ok, "pass_rate": ok / 10.0, "timeouts": sum(1 for c in cases if c["timeout"])}


def _run_dyck_suite_live(project_id: str, agent_id: str, timeout_sec: int = 30) -> dict:
    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    cases_src = [
        ("([])", True),
        ("([[]])", True),
        ("([)]", False),
        ("(([]))", True),
        ("([[[[]]]])", True),
        ("([][])(())", True),
        ("([)", False),
        ("(()[]][)", False),
        ("[([]())]", True),
        ("([[[)]])", False),
        ("(([[[]]])())", True),
        ("([[[[]]]]]", False),
    ]
    cases_src = cases_src[:10]
    ok = 0
    cases = []
    for i, (seq, expect) in enumerate(cases_src, start=1):
        _, ans, to = _run_agent_once_with_timeout(
            agent,
            _state(project_id, f"DYCK2难度{i}/10: 串={seq}。只回复 OK 或 BAD。"),
            timeout_sec=timeout_sec,
        )
        low = ans.lower()
        got = ("ok" in low) and ("bad" not in low)
        passed = got == expect
        ok += int(passed)
        cases.append({"idx": i, "seq": seq, "expect_ok": expect, "ans": ans[:120], "pass": passed, "timeout": bool(to)})
    return {"cases": cases, "pass_count": ok, "pass_rate": ok / 10.0, "timeouts": sum(1 for c in cases if c["timeout"])}


def _write_live_strict_report(rounds: int, rows: list[dict]) -> Path:
    overall = {
        "rounds": rounds,
        "tool_called_any_rate_avg": sum(float(r["tool_coverage"]["called_any_rate"]) for r in rows) / max(1, len(rows)),
        "tool_called_ok_rate_avg": sum(float(r["tool_coverage"]["called_ok_rate"]) for r in rows) / max(1, len(rows)),
        "memory_300_pass_rate_avg": sum(float(r["memory_300"]["pass_rate"]) for r in rows) / max(1, len(rows)),
        "restate_pass_rate_avg": sum(float(r["restate_10"]["pass_rate"]) for r in rows) / max(1, len(rows)),
        "assoc_pass_rate_avg": sum(float(r["assoc_10"]["pass_rate"]) for r in rows) / max(1, len(rows)),
        "dyck_pass_rate_avg": sum(float(r["dyck_10"]["pass_rate"]) for r in rows) / max(1, len(rows)),
        "benchmark_completeness_rate": sum(
            1
            for r in rows
            if (
                int(r["tool_coverage"]["called_any_count"]) == int(r["tool_coverage"]["tool_count"])
                and len(r["memory_300"]["cases"]) == 10
                and len(r["restate_10"]["cases"]) == 10
                and len(r["assoc_10"]["cases"]) == 10
                and len(r["dyck_10"]["cases"]) == 10
            )
        )
        / max(1, len(rows)),
        "timeouts_total": sum(
            int(r["tool_coverage"]["timeouts"])
            + int(r["memory_300"]["timeouts"])
            + int(r["restate_10"]["timeouts"])
            + int(r["assoc_10"]["timeouts"])
            + int(r["dyck_10"]["timeouts"])
            for r in rows
        ),
    }
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "live_llm_strict",
        "rounds": rounds,
        "overall": overall,
        "per_round": rows,
    }
    out = Path("reports")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "agent_cognitive_benchmark_live_strict_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _run_one_round_live_strict(round_idx: int) -> dict:
    project_id, agent_id = _mk_project(round_idx)
    old = _setup_config(project_id, agent_id)
    rng = random.Random(20260216 + round_idx)
    timeout_sec = max(5, int(os.getenv("AGENT_BENCH_LIVE_STRICT_TIMEOUT_SEC", "35")))
    try:
        tool_cov = _run_tool_coverage_suite_live(project_id, agent_id, timeout_sec=timeout_sec)
        mem = _run_memory_300_suite_live(project_id, agent_id, rng=rng, timeout_sec=timeout_sec)
        rest = _run_restate_suite_live(project_id, agent_id, timeout_sec=timeout_sec)
        assoc = _run_assoc_suite_live(project_id, agent_id, timeout_sec=timeout_sec)
        dyck = _run_dyck_suite_live(project_id, agent_id, timeout_sec=timeout_sec)
        return {
            "round": round_idx,
            "project_id": project_id,
            "tool_coverage": tool_cov,
            "memory_300": mem,
            "restate_10": rest,
            "assoc_10": assoc,
            "dyck_10": dyck,
        }
    finally:
        _cleanup(project_id, old)


def test_agent_cognitive_benchmark_report():
    enabled = str(os.getenv("AGENT_BENCH_DETERMINISTIC", "0")).strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        pytest.skip("deterministic cognitive benchmark disabled; set AGENT_BENCH_DETERMINISTIC=1 to enable")
    rounds = max(1, int(os.getenv("AGENT_BENCH_ROUNDS", "5")))
    rows = [_run_one_round(i + 1) for i in range(rounds)]
    report_path = _write_report(rounds, rows)

    # Baseline thresholds for framework-level deterministic benchmark.
    overall = json.loads(report_path.read_text(encoding="utf-8"))["overall"]
    assert overall["tool_flow_pass_rate"] >= 1.0
    assert overall["memory_pass_rate"] >= 1.0
    assert overall["restate_pass_rate"] >= 1.0
    assert overall["assoc_pass_rate"] >= 1.0
    assert overall["avg_dyck_pass_rate"] >= 1.0


def test_agent_cognitive_benchmark_live_report():
    live = str(os.getenv("AGENT_BENCH_LIVE", "0")).strip().lower() in {"1", "true", "yes", "on"}
    if not live:
        pytest.skip("live benchmark disabled; set AGENT_BENCH_LIVE=1 to enable")
    api_key = str(getattr(runtime_config, "openrouter_api_key", "") or "").strip()
    if not api_key:
        pytest.skip("live benchmark requires OPENROUTER_API_KEY in runtime config")

    rounds = max(1, int(os.getenv("AGENT_BENCH_LIVE_ROUNDS", "3")))
    workers = max(1, int(os.getenv("AGENT_BENCH_LIVE_WORKERS", "1")))
    if workers <= 1 or rounds == 1:
        rows = [_run_one_round_live(i + 1) for i in range(rounds)]
    else:
        rows_map: dict[int, dict] = {}
        with ThreadPoolExecutor(max_workers=min(workers, rounds)) as ex:
            futs = {ex.submit(_run_one_round_live, i + 1): (i + 1) for i in range(rounds)}
            for fut in as_completed(futs):
                idx = futs[fut]
                rows_map[idx] = fut.result()
        rows = [rows_map[i + 1] for i in range(rounds)]
    report_path = _write_live_report(rounds, rows)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload.get("mode") == "live_llm"
    assert int(payload.get("rounds", 0)) == rounds
    assert len(payload.get("per_round", [])) == rounds


def test_agent_cognitive_benchmark_live_strict_report():
    strict = str(os.getenv("AGENT_BENCH_LIVE_STRICT", "0")).strip().lower() in {"1", "true", "yes", "on"}
    if not strict:
        pytest.skip("strict live benchmark disabled; set AGENT_BENCH_LIVE_STRICT=1 to enable")
    api_key = str(getattr(runtime_config, "openrouter_api_key", "") or "").strip()
    if not api_key:
        pytest.skip("strict live benchmark requires OPENROUTER_API_KEY in runtime config")

    rounds = max(1, int(os.getenv("AGENT_BENCH_LIVE_STRICT_ROUNDS", "10")))
    workers = max(1, int(os.getenv("AGENT_BENCH_LIVE_STRICT_WORKERS", "1")))
    if workers <= 1 or rounds == 1:
        rows = [_run_one_round_live_strict(i + 1) for i in range(rounds)]
    else:
        rows_map: dict[int, dict] = {}
        with ThreadPoolExecutor(max_workers=min(workers, rounds)) as ex:
            futs = {ex.submit(_run_one_round_live_strict, i + 1): (i + 1) for i in range(rounds)}
            for fut in as_completed(futs):
                idx = futs[fut]
                rows_map[idx] = fut.result()
        rows = [rows_map[i + 1] for i in range(rounds)]
    report_path = _write_live_strict_report(rounds, rows)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload.get("mode") == "live_llm_strict"
    assert int(payload.get("rounds", 0)) == rounds
    assert len(payload.get("per_round", [])) == rounds
    for row in payload.get("per_round", []):
        cov = row.get("tool_coverage", {})
        assert int(cov.get("called_any_count", 0)) == int(cov.get("tool_count", 0))
        assert list(cov.get("missing_any", [])) == []
        assert len(row.get("memory_300", {}).get("cases", [])) == 10
        assert len(row.get("restate_10", {}).get("cases", [])) == 10
        assert len(row.get("assoc_10", {}).get("cases", [])) == 10
        assert len(row.get("dyck_10", {}).get("cases", [])) == 10
