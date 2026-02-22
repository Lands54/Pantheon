from __future__ import annotations

import json
import time
import uuid

from api.services import project_service
from gods.angelia import store as angelia_store
from gods.angelia import sync_council
from gods.config import runtime_config
from gods.config.models import AgentModelConfig
from gods.events import EventRecord, append_event, list_events
from gods.paths import project_dir, runtime_dir


def _pid() -> str:
    return f"it_roberts_{uuid.uuid4().hex[:8]}"


def test_roberts_sync_council_end_to_end_simulation():
    pid = _pid()
    agents = ["a1", "a2", "a3"]
    try:
        project_service.create_project(pid)
        pdir = project_dir(pid)
        for aid in agents:
            (pdir / "agents" / aid).mkdir(parents=True, exist_ok=True)
            pf = pdir / "mnemosyne" / "agent_profiles" / f"{aid}.md"
            pf.parent.mkdir(parents=True, exist_ok=True)
            pf.write_text(f"agent {aid}", encoding="utf-8")

        proj = runtime_config.projects[pid]
        proj.active_agents = list(agents)
        cur = dict(proj.agent_settings or {})
        for aid in agents:
            if aid not in cur or not isinstance(cur.get(aid), AgentModelConfig):
                cur[aid] = AgentModelConfig()
        proj.agent_settings = cur
        runtime_config.save()

        st = project_service.sync_council_start(
            project_id=pid,
            title="生态协商",
            content="讨论接口与节奏",
            participants=agents,
            cycles=1,
            initiator="human.overseer",
            rules_profile="roberts_core_v1",
            agenda=[{"id": "agenda_1", "title": "生态协商", "description": "接口对齐"}],
            timeouts={"speaker": 60, "action": 60, "vote": 90},
        )["sync_council"]
        assert st["phase"] == "collecting"

        for aid in agents:
            project_service.sync_council_confirm(project_id=pid, agent_id=aid)

        rt = runtime_dir(pid)
        (rt / "angelia_agents.json").write_text(
            json.dumps({"a1": {"run_state": "idle"}, "a2": {"run_state": "idle"}, "a3": {"run_state": "idle"}}),
            encoding="utf-8",
        )
        st = sync_council.tick(pid, "a1", has_queued=False)
        assert st["phase"] == "in_session"
        assert st["current_speaker"] == "a1"

        evt = append_event(
            EventRecord.create(
                project_id=pid,
                domain="angelia",
                event_type="manual",
                priority=80,
                payload={"agent_id": "a1", "reason": "manual_test"},
            )
        )
        _ = angelia_store.pick_batch_events(
            project_id=pid,
            agent_id="a1",
            now=time.time(),
            cooldown_until=0,
            preempt_types=set(),
            limit=5,
            force_after_sec=0,
        )
        st = project_service.sync_council_status(pid)["sync_council"]
        assert evt.event_id in set(st.get("deferred_event_ids", []))

        project_service.sync_council_action(project_id=pid, actor_id="a1", action_type="motion_submit", payload={"text": "通过统一接口 v1"})
        project_service.sync_council_action(project_id=pid, actor_id="a2", action_type="motion_second", payload={})
        project_service.sync_council_action(project_id=pid, actor_id="a1", action_type="procedural_call_question", payload={})
        project_service.sync_council_action(project_id=pid, actor_id="a1", action_type="vote_cast", payload={"choice": "yes"})
        project_service.sync_council_action(project_id=pid, actor_id="a2", action_type="vote_cast", payload={"choice": "yes"})
        project_service.sync_council_action(project_id=pid, actor_id="a3", action_type="vote_cast", payload={"choice": "no"})

        resolutions = project_service.sync_council_resolutions(project_id=pid, limit=10).get("rows", [])
        assert resolutions
        r0 = resolutions[0]
        assert r0.get("decision") in {"adopted", "rejected"}
        assert isinstance(r0.get("execution_tasks"), list)
        assert isinstance(r0.get("hermes_contract_draft"), dict)

        project_service.sync_council_chair(project_id=pid, action="terminate", actor_id="human.overseer")

        rows = list_events(project_id=pid, event_type="manual", state=None, limit=10, agent_id="a1")
        m = None
        for row in rows:
            if row.event_id == evt.event_id:
                m = dict(row.meta or {})
                break
        assert isinstance(m, dict)
        assert m.get("deferred_by_council") is False
        assert m.get("deferred_released_at")

        led = project_service.sync_council_ledger(project_id=pid, since_seq=0, limit=200).get("rows", [])
        assert len(led) >= 8
    finally:
        try:
            project_service.delete_project(pid)
        except Exception:
            pass
