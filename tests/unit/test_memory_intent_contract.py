from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from gods.mnemosyne import MemoryIntent, record_intent
from gods.mnemosyne.facade import intent_from_tool_call, intent_from_tool_result


def test_record_intent_rejects_invalid_llm_payload_missing_field():
    project_id = f"mn_intent_contract_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        with pytest.raises(ValueError, match="llm.response"):
            record_intent(
                MemoryIntent(
                    intent_key="llm.response",
                    project_id=project_id,
                    agent_id="alpha",
                    source_kind="llm",
                    payload={"phase": "freeform"},
                    fallback_text="x",
                )
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_record_intent_rejects_tool_key_payload_mismatch():
    project_id = f"mn_intent_contract_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        with pytest.raises(ValueError, match="payload.tool_name"):
            record_intent(
                MemoryIntent(
                    intent_key="tool.read.ok",
                    project_id=project_id,
                    agent_id="alpha",
                    source_kind="tool",
                    payload={
                        "tool_name": "write_file",
                        "status": "ok",
                        "args": {},
                        "result": "ok",
                        "result_compact": "ok",
                    },
                    fallback_text="x",
                )
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_record_intent_accepts_valid_tool_contract_from_builder():
    project_id = f"mn_intent_contract_{uuid.uuid4().hex[:8]}"
    agent_id = "alpha"
    base = Path("projects") / project_id
    try:
        intent = intent_from_tool_result(
            project_id=project_id,
            agent_id=agent_id,
            tool_name="list",
            status="ok",
            args={"path": "."},
            result="[DIR] done",
        )
        out = record_intent(intent)
        assert out["intent_key"] == "tool.list.ok"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_record_intent_accepts_valid_tool_call_contract_from_builder():
    project_id = f"mn_intent_contract_{uuid.uuid4().hex[:8]}"
    agent_id = "alpha"
    base = Path("projects") / project_id
    try:
        intent = intent_from_tool_call(
            project_id=project_id,
            agent_id=agent_id,
            tool_name="list",
            args={"path": "."},
            node_name="dispatch_tools",
            call_id="call_test_001",
        )
        out = record_intent(intent)
        assert out["intent_key"] == "tool.call.list"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_record_intent_accepts_valid_inbox_notice_contract():
    project_id = f"mn_intent_contract_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        out = record_intent(
            MemoryIntent(
                intent_key="inbox.notice.contract_commit_notice",
                project_id=project_id,
                agent_id="alpha",
                source_kind="inbox",
                payload={
                    "title": "t",
                    "sender": "s",
                    "message_id": "m1",
                    "msg_type": "contract_commit_notice",
                    "content": "hello",
                    "payload": {},
                },
                fallback_text="x",
            )
        )
        assert out["intent_key"] == "inbox.notice.contract_commit_notice"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_record_intent_rejects_invalid_event_contract():
    project_id = f"mn_intent_contract_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        with pytest.raises(ValueError, match="payload.event_type"):
            record_intent(
                MemoryIntent(
                    intent_key="event.mail_event",
                    project_id=project_id,
                    agent_id="alpha",
                    source_kind="event",
                    payload={
                        "stage": "processing",
                        "event_id": "e1",
                        "event_type": "timer",
                        "priority": 100,
                        "attempt": 0,
                        "max_attempts": 3,
                        "payload": {},
                    },
                    fallback_text="x",
                )
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_record_intent_rejects_invalid_phase_retry_contract():
    project_id = f"mn_intent_contract_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        with pytest.raises(ValueError, match="payload.phase"):
            record_intent(
                MemoryIntent(
                    intent_key="phase.retry.act",
                    project_id=project_id,
                    agent_id="alpha",
                    source_kind="phase",
                    payload={"phase": "reason", "message": "retry"},
                    fallback_text="x",
                )
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)
