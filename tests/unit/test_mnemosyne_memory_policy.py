from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from gods.mnemosyne import (
    MemoryIntent,
    MemoryPolicyMissingError,
    MemoryTemplateMissingError,
    ensure_memory_policy,
    validate_memory_policy,
    record_intent,
    template_vars_for_intent,
)


def test_record_intent_llm_response_writes_chronicle():
    project_id = f"mn_policy_{uuid.uuid4().hex[:8]}"
    agent_id = "alpha"
    base = Path("projects") / project_id
    try:
        result = record_intent(
            MemoryIntent(
                intent_key="llm.response",
                project_id=project_id,
                agent_id=agent_id,
                source_kind="llm",
                payload={"phase": "freeform", "content": "hello chronicle"},
                fallback_text="hello chronicle",
            )
        )
        chronicle = base / "mnemosyne" / "chronicles" / f"{agent_id}.md"
        assert chronicle.exists()
        text = chronicle.read_text(encoding="utf-8")
        assert "hello chronicle" in text
        assert result["chronicle_written"] is True
        assert result["runtime_log_written"] is False
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_record_intent_inbox_ack_runtime_only():
    project_id = f"mn_policy_{uuid.uuid4().hex[:8]}"
    agent_id = "beta"
    base = Path("projects") / project_id
    try:
        result = record_intent(
            MemoryIntent(
                intent_key="inbox.read_ack",
                project_id=project_id,
                agent_id=agent_id,
                source_kind="inbox",
                payload={"event_ids": ["e1", "e2"], "count": 2},
                fallback_text="ack",
            )
        )
        chronicle = base / "mnemosyne" / "chronicles" / f"{agent_id}.md"
        runtime_log = base / "mnemosyne" / "runtime_events" / f"{agent_id}.jsonl"
        assert not chronicle.exists()
        assert runtime_log.exists()
        rows = [json.loads(line) for line in runtime_log.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(rows) == 1
        assert rows[0]["intent_key"] == "inbox.read_ack"
        assert "payload=" in rows[0]["text"]
        assert result["chronicle_written"] is False
        assert result["runtime_log_written"] is True
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_missing_policy_key_is_auto_reconciled():
    project_id = f"mn_policy_{uuid.uuid4().hex[:8]}"
    agent_id = "gamma"
    base = Path("projects") / project_id
    try:
        ensure_memory_policy(project_id)
        policy_file = base / "mnemosyne" / "memory_policy.json"
        policy = json.loads(policy_file.read_text(encoding="utf-8"))
        policy.pop("llm.response", None)
        policy_file.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

        result = record_intent(
            MemoryIntent(
                intent_key="llm.response",
                project_id=project_id,
                agent_id=agent_id,
                source_kind="llm",
                payload={"phase": "x", "content": "x"},
                fallback_text="x",
            )
        )
        assert result["intent_key"] == "llm.response"
        policy_after = json.loads(policy_file.read_text(encoding="utf-8"))
        assert "llm.response" in policy_after
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_missing_template_raises():
    project_id = f"mn_policy_{uuid.uuid4().hex[:8]}"
    agent_id = "delta"
    base = Path("projects") / project_id
    try:
        ensure_memory_policy(project_id)
        policy_file = base / "mnemosyne" / "memory_policy.json"
        policy = json.loads(policy_file.read_text(encoding="utf-8"))
        policy["llm.response"]["chronicle_template_key"] = "memory_template_not_found"
        policy_file.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

        try:
            record_intent(
                MemoryIntent(
                    intent_key="llm.response",
                    project_id=project_id,
                    agent_id=agent_id,
                    source_kind="llm",
                    payload={"phase": "x", "content": "x"},
                    fallback_text="x",
                )
            )
            assert False, "expected MemoryTemplateMissingError"
        except MemoryTemplateMissingError:
            pass
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_chronicle_enabled_without_template_raises():
    project_id = f"mn_policy_{uuid.uuid4().hex[:8]}"
    agent_id = "eta"
    base = Path("projects") / project_id
    try:
        ensure_memory_policy(project_id)
        policy_file = base / "mnemosyne" / "memory_policy.json"
        policy = json.loads(policy_file.read_text(encoding="utf-8"))
        policy["llm.response"]["to_chronicle"] = True
        policy["llm.response"]["chronicle_template_key"] = ""
        policy_file.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            record_intent(
                MemoryIntent(
                    intent_key="llm.response",
                    project_id=project_id,
                    agent_id=agent_id,
                    source_kind="llm",
                    payload={"phase": "x", "content": "x"},
                    fallback_text="x",
                )
            )
            assert False, "expected MemoryTemplateMissingError"
        except MemoryTemplateMissingError:
            pass
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_split_templates_chronicle_and_runtime():
    project_id = f"mn_policy_{uuid.uuid4().hex[:8]}"
    agent_id = "epsilon"
    base = Path("projects") / project_id
    try:
        ensure_memory_policy(project_id)
        policy_file = base / "mnemosyne" / "memory_policy.json"
        policy = json.loads(policy_file.read_text(encoding="utf-8"))
        policy["llm.response"]["to_runtime_log"] = True
        policy["llm.response"]["chronicle_template_key"] = "memory_llm_response"
        policy["llm.response"]["runtime_log_template_key"] = ""
        policy_file.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

        result = record_intent(
            MemoryIntent(
                intent_key="llm.response",
                project_id=project_id,
                agent_id=agent_id,
                source_kind="llm",
                payload={"phase": "x", "content": "split-check"},
                fallback_text="fallback-split",
            )
        )
        chronicle = base / "mnemosyne" / "chronicles" / f"{agent_id}.md"
        runtime_log = base / "mnemosyne" / "runtime_events" / f"{agent_id}.jsonl"
        assert chronicle.exists()
        assert runtime_log.exists()
        chrono_text = chronicle.read_text(encoding="utf-8")
        rows = [json.loads(line) for line in runtime_log.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert "split-check" in chrono_text
        assert "payload=" in rows[-1]["text"]
        assert "split-check" in rows[-1]["text"]
        assert result["chronicle_text"] != result["runtime_text"]
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_unknown_intent_auto_appended_runtime_only():
    project_id = f"mn_policy_{uuid.uuid4().hex[:8]}"
    agent_id = "zeta"
    base = Path("projects") / project_id
    try:
        ensure_memory_policy(project_id)
        result = record_intent(
            MemoryIntent(
                intent_key="event.custom_new_signal",
                project_id=project_id,
                agent_id=agent_id,
                source_kind="event",
                payload={"k": "v"},
                fallback_text="custom signal",
            )
        )
        assert result["chronicle_written"] is False
        assert result["runtime_log_written"] is True
        policy_file = base / "mnemosyne" / "memory_policy.json"
        policy = json.loads(policy_file.read_text(encoding="utf-8"))
        rule = policy.get("event.custom_new_signal") or {}
        assert rule.get("to_chronicle") is False
        assert rule.get("to_runtime_log") is True
        assert str(rule.get("chronicle_template_key", "")) == ""
        assert str(rule.get("runtime_log_template_key", "")) == ""
        vars_info = template_vars_for_intent(project_id, "event.custom_new_signal")
        assert "project_id" in vars_info["guaranteed_vars"]
        assert "k" in vars_info["observed_vars"]
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_legacy_template_fields_rejected():
    project_id = f"mn_policy_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        ensure_memory_policy(project_id)
        policy_file = base / "mnemosyne" / "memory_policy.json"
        policy = json.loads(policy_file.read_text(encoding="utf-8"))
        policy["llm.response"]["template_chronicle"] = "legacy_key"
        policy_file.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            validate_memory_policy(project_id, ensure_exists=False)
            assert False, "expected MemoryPolicyMissingError"
        except MemoryPolicyMissingError:
            pass
    finally:
        shutil.rmtree(base, ignore_errors=True)
