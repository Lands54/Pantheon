"""Project lifecycle/report use-case service."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from gods.angelia import facade as angelia_facade
from gods.angelia import sync_council as angelia_sync_council
from gods.config import ProjectConfig, runtime_config
from gods.iris import facade as iris_facade
from gods.mnemosyne import facade as mnemosyne_facade
from gods.mnemosyne import template_registry as mnemosyne_templates
from gods.project import build_project_report, load_project_report
from gods.protocols import build_knowledge_graph
from gods.runtime import facade as runtime_facade
from gods.paths import runtime_debug_dir


class ProjectService:
    @staticmethod
    def _read_latest_jsonl_row(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        last_line = ""
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line.strip()
        if not last_line:
            return None
        try:
            row = json.loads(last_line)
        except Exception:
            return None
        return row if isinstance(row, dict) else None

    @staticmethod
    def _ensure_project_layout(project_root: Path):
        runtime = project_root / "runtime"
        mnemosyne = project_root / "mnemosyne"
        (runtime / "locks").mkdir(parents=True, exist_ok=True)
        (mnemosyne / "agent_profiles").mkdir(parents=True, exist_ok=True)
        (project_root / "agents").mkdir(parents=True, exist_ok=True)
        (project_root / "buffers").mkdir(parents=True, exist_ok=True)

        events_file = runtime / "events.jsonl"
        detach_file = runtime / "detach_jobs.jsonl"
        policy_file = mnemosyne / "memory_policy.json"
        runtime_tpl_file = mnemosyne / "runtime_log_templates.json"
        chronicle_tpl_file = mnemosyne / "chronicle_templates.json"
        if not events_file.exists():
            events_file.write_text("", encoding="utf-8")
        if not detach_file.exists():
            detach_file.write_text("", encoding="utf-8")
        required_keys = set(mnemosyne_facade.required_intent_keys())
        should_rewrite_policy = not policy_file.exists()
        if not should_rewrite_policy:
            try:
                raw = json.loads(policy_file.read_text(encoding="utf-8"))
                if not isinstance(raw, dict) or not required_keys.issubset(set(raw.keys())):
                    should_rewrite_policy = True
            except Exception:
                should_rewrite_policy = True
        if should_rewrite_policy:
            payload = mnemosyne_facade.default_memory_policy()
            policy_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if not runtime_tpl_file.exists() or not chronicle_tpl_file.exists():
            mnemosyne_templates.ensure_memory_templates(project_root.name)

    @staticmethod
    def _scaffold_project_root(project_id: str):
        root = Path("projects")
        root.mkdir(parents=True, exist_ok=True)
        project_root = root / project_id
        template_root = root / "templates" / "default"
        if template_root.exists():
            shutil.copytree(template_root, project_root, dirs_exist_ok=True)
        else:
            project_root.mkdir(parents=True, exist_ok=True)
        ProjectService._ensure_project_layout(project_root)

    def list_projects(self) -> dict[str, Any]:
        return {"projects": runtime_config.projects, "current": runtime_config.current_project}

    def create_project(self, pid: str) -> dict[str, str]:
        if not pid:
            raise HTTPException(status_code=400, detail="Project id is required")
        if pid in runtime_config.projects:
            return {"error": "Project exists"}

        runtime_config.projects[pid] = ProjectConfig()
        runtime_config.save()
        # Create project root from templates/default and enforce current runtime layout.
        self._scaffold_project_root(pid)
        return {"status": "success"}

    def delete_project(self, project_id: str) -> dict[str, str]:
        if project_id == "default":
            raise HTTPException(status_code=400, detail="Cannot delete default world")
        if project_id not in runtime_config.projects:
            raise HTTPException(status_code=404, detail="Project not found")

        # Stop project workers first to avoid runtime-dir deletion race.
        try:
            angelia_facade.stop_project_workers(project_id)
        except Exception:
            pass

        proj = runtime_config.projects[project_id]
        proj.simulation_enabled = False
        del runtime_config.projects[project_id]
        if runtime_config.current_project == project_id:
            runtime_config.current_project = "default"
        runtime_config.save()

        proj_dir = Path("projects") / project_id
        if proj_dir.exists():
            # Runtime/worker threads may still flush final files; retry briefly.
            last_err: Exception | None = None
            for _ in range(5):
                try:
                    shutil.rmtree(proj_dir)
                    last_err = None
                    break
                except OSError as e:
                    last_err = e
                    time.sleep(0.05)
            if last_err is not None and proj_dir.exists():
                raise HTTPException(status_code=500, detail=f"failed to delete project directory: {last_err}")
        return {"status": "success"}

    def ensure_exists(self, project_id: str):
        if project_id not in runtime_config.projects:
            raise HTTPException(status_code=404, detail="Project not found")

    def rebuild_knowledge(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        graph = build_knowledge_graph(project_id)
        return {
            "status": "success",
            "project_id": project_id,
            "nodes": len(graph.get("nodes", [])),
            "edges": len(graph.get("edges", [])),
            "output": f"projects/{project_id}/knowledge/knowledge_graph.json",
        }

    def start_project(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        target = runtime_config.projects[project_id]
        requires_docker = bool(getattr(target, "docker_enabled", True)) and str(
            getattr(target, "command_executor", "local")
        ) == "docker"
        if requires_docker:
            ok, msg = runtime_facade.docker_available()
            if not ok:
                # Hard guard: never keep simulation enabled when docker runtime is unavailable.
                target.simulation_enabled = False
                runtime_config.save()
                raise HTTPException(
                    status_code=503,
                    detail=f"Docker unavailable. Project '{project_id}' stopped: {msg}",
                )

        # Single-active-project runtime policy: starting one project pauses all others.
        for pid, proj in runtime_config.projects.items():
            proj.simulation_enabled = pid == project_id

        runtime_config.current_project = project_id
        proj = runtime_config.projects[project_id]
        runtime_info = {"enabled": False, "ensured": []}
        if bool(getattr(proj, "docker_enabled", True)) and str(getattr(proj, "command_executor", "local")) == "docker":
            if bool(getattr(proj, "docker_auto_start_on_project_start", True)):
                ok, msg = runtime_facade.docker_available()
                runtime_info = {"enabled": True, "available": ok, "detail": msg, "ensured": []}
                if ok:
                    for aid in proj.active_agents:
                        try:
                            st = runtime_facade.ensure_agent_runtime(project_id, aid)
                            runtime_info["ensured"].append(
                                {
                                    "agent_id": aid,
                                    "running": st.running,
                                    "exists": st.exists,
                                    "container_name": st.container_name,
                                }
                            )
                        except Exception as e:
                            runtime_info["ensured"].append({"agent_id": aid, "error": str(e)})
        runtime_config.save()
        try:
            for aid in proj.active_agents:
                angelia_facade.enqueue_event(
                    project_id=project_id,
                    agent_id=aid,
                    event_type="system",
                    payload={"agent_id": aid, "reason": "project_started"},
                    priority=angelia_facade.get_priority_weights(project_id).get("system", 60),
                    dedupe_key=f"project_started:{aid}",
                )
        except Exception:
            pass
        return {
            "status": "success",
            "project_id": project_id,
            "simulation_enabled": True,
            "current_project": runtime_config.current_project,
            "runtime": runtime_info,
        }

    def stop_project(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        proj = runtime_config.projects[project_id]
        proj.simulation_enabled = False
        runtime_info = {"stopped": []}
        if bool(getattr(proj, "docker_enabled", True)) and str(getattr(proj, "command_executor", "local")) == "docker":
            if bool(getattr(proj, "docker_auto_stop_on_project_stop", True)):
                for aid in proj.active_agents:
                    runtime_facade.stop_agent_runtime(project_id, aid)
                    runtime_info["stopped"].append(aid)
        runtime_config.save()
        return {
            "status": "success",
            "project_id": project_id,
            "simulation_enabled": False,
            "current_project": runtime_config.current_project,
            "runtime": runtime_info,
        }

    def runtime_status(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        proj = runtime_config.projects[project_id]
        rows = runtime_facade.list_project_runtimes(project_id, proj.active_agents)
        ok, msg = runtime_facade.docker_available()
        return {"project_id": project_id, "docker_available": ok, "docker_detail": msg, "agents": rows}

    def runtime_restart_agent(self, project_id: str, agent_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        proj = runtime_config.projects[project_id]
        if agent_id not in proj.active_agents:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' is not active in project '{project_id}'")
        ok, msg = runtime_facade.docker_available()
        if not ok:
            raise HTTPException(status_code=503, detail=f"Docker unavailable: {msg}")
        st = runtime_facade.restart_agent_runtime(project_id, agent_id)
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "exists": st.exists,
            "running": st.running,
            "image": st.image,
            "container_name": st.container_name,
            "container_id": st.container_id,
        }

    def runtime_reconcile(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        proj = runtime_config.projects[project_id]
        ok, msg = runtime_facade.docker_available()
        if not ok:
            raise HTTPException(status_code=503, detail=f"Docker unavailable: {msg}")
        return runtime_facade.reconcile_project(project_id, proj.active_agents)

    def detach_submit(self, project_id: str, agent_id: str, command: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        try:
            return runtime_facade.detach_submit(project_id=project_id, agent_id=agent_id, command=command)
        except runtime_facade.DetachError as e:
            raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}") from e

    def detach_list(self, project_id: str, agent_id: str, status: str, limit: int) -> dict[str, Any]:
        self.ensure_exists(project_id)
        try:
            return runtime_facade.detach_list_for_api(project_id=project_id, agent_id=agent_id, status=status, limit=limit)
        except runtime_facade.DetachError as e:
            raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}") from e

    def detach_stop(self, project_id: str, job_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        try:
            return runtime_facade.detach_stop(project_id=project_id, job_id=job_id, reason="manual")
        except runtime_facade.DetachError as e:
            raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}") from e

    def detach_reconcile(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        try:
            return runtime_facade.detach_reconcile(project_id=project_id)
        except runtime_facade.DetachError as e:
            raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}") from e

    def detach_logs(self, project_id: str, job_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        try:
            return runtime_facade.detach_get_logs(project_id=project_id, job_id=job_id)
        except runtime_facade.DetachError as e:
            raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}") from e

    def sync_council_start(
        self,
        *,
        project_id: str,
        title: str,
        content: str,
        participants: list[str],
        cycles: int,
        initiator: str = "human.overseer",
    ) -> dict[str, Any]:
        self.ensure_exists(project_id)
        proj = runtime_config.projects[project_id]
        active = {
            str(x).strip()
            for x in list(getattr(proj, "active_agents", []) or [])
            if str(x).strip()
        }
        members = [str(x).strip() for x in list(participants or []) if str(x).strip()]
        if not members:
            raise HTTPException(status_code=400, detail="participants is required")
        illegal = [x for x in members if x not in active]
        if illegal:
            raise HTTPException(
                status_code=400,
                detail=f"participants must be active agents. invalid={','.join(illegal)}",
            )
        try:
            state = angelia_sync_council.start_session(
                project_id,
                title=title,
                content=content,
                participants=members,
                cycles=max(1, int(cycles or 1)),
                initiator=str(initiator or "human.overseer"),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"project_id": project_id, "status": "started", "sync_council": state}

    def sync_council_confirm(self, *, project_id: str, agent_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        aid = str(agent_id or "").strip()
        if not aid:
            raise HTTPException(status_code=400, detail="agent_id is required")
        try:
            state = angelia_sync_council.confirm_participant(project_id, aid)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"project_id": project_id, "status": "confirmed", "sync_council": state}

    def sync_council_status(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        state = angelia_sync_council.get_state(project_id)
        return {"project_id": project_id, "sync_council": state}

    def build_report(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        # Report builder also archives markdown into Mnemosyne human vault.
        report = build_project_report(project_id)
        return {
            "status": "success",
            "project_id": project_id,
            "protocol_count": report.get("protocol_count", 0),
            "invocation_count": report.get("invocation_count", 0),
            "protocol_execution_validation": report.get("protocol_execution_validation", {}),
            "top_protocols": report.get("top_protocols", []),
            "output": report.get("output", {}),
            "mnemosyne_entry_id": report.get("mnemosyne_entry_id", ""),
        }

    def context_preview(self, project_id: str, agent_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        row = mnemosyne_facade.latest_context_report(project_id, agent_id)
        if not isinstance(row, dict):
            entries = mnemosyne_facade.list_pulse_entries(project_id, agent_id, from_seq=0, limit=500)
            frames = mnemosyne_facade.group_pulses(entries)
            row = {
                "strategy_used": "pulse_ledger_only",
                "preview": {
                    "pulse_count": len(frames),
                    "entry_count": len(entries),
                },
            }
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "preview": row,
        }

    def context_reports(self, project_id: str, agent_id: str, limit: int) -> dict[str, Any]:
        self.ensure_exists(project_id)
        rows = mnemosyne_facade.list_context_reports(project_id, agent_id, limit=max(1, min(limit, 500)))
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "reports": rows,
        }

    def context_llm_latest(self, project_id: str, agent_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        trace_file = runtime_debug_dir(project_id, agent_id) / "llm_io.jsonl"
        row = self._read_latest_jsonl_row(trace_file)
        if not row:
            return {
                "project_id": project_id,
                "agent_id": agent_id,
                "available": False,
                "trace": None,
            }
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "available": True,
            "trace": row,
        }

    def context_snapshot(self, project_id: str, agent_id: str, since_intent_seq: int = 0) -> dict[str, Any]:
        self.ensure_exists(project_id)
        since = max(0, int(since_intent_seq or 0))
        entries = mnemosyne_facade.list_pulse_entries(
            project_id,
            agent_id,
            from_seq=since,
            limit=5000,
        )
        frames = mnemosyne_facade.group_pulses(entries)
        # Delta windows (from_seq > 0) can naturally clip pulse.start.
        # Discard incomplete head/middle frames before integrity checks to avoid
        # surfacing truncation artifacts as false errors in UI.
        if since > 0:
            frames = mnemosyne_facade.discard_incomplete_frames(frames)
        report = mnemosyne_facade.validate_pulse_integrity(frames)
        latest_seq = int(entries[-1].get("seq", 0) or 0) if entries else since
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "available": bool(entries),
            "mode": "pulse_ledger",
            "base_intent_seq": latest_seq,
            "token_estimate": 0,
            "entries": entries,
            "pulses": [
                {
                    "pulse_id": fr.pulse_id,
                    "start": fr.start,
                    "triggers": fr.triggers,
                    "llm": fr.llm,
                    "tools": fr.tools,
                    "finish": fr.finish,
                }
                for fr in frames
            ],
            "errors": report.errors,
            "warnings": report.warnings,
            "stats": {
                "entry_count": len(entries),
                "pulse_count": len(frames),
                "since_seq": since,
            },
        }

    def context_snapshot_compressions(self, project_id: str, agent_id: str, limit: int = 50) -> dict[str, Any]:
        self.ensure_exists(project_id)
        rows = []
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "items": rows,
            "count": len(rows),
            "deprecated": True,
        }

    def context_snapshot_derived(self, project_id: str, agent_id: str, limit: int = 100) -> dict[str, Any]:
        self.ensure_exists(project_id)
        rows = []
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "items": rows,
            "count": len(rows),
            "deprecated": True,
        }

    def context_pulses(self, project_id: str, agent_id: str, from_seq: int = 0, limit: int = 500) -> dict[str, Any]:
        self.ensure_exists(project_id)
        from_seq = max(0, int(from_seq or 0))
        entries = mnemosyne_facade.list_pulse_entries(
            project_id,
            agent_id,
            from_seq=from_seq,
            limit=max(1, min(int(limit or 500), 5000)),
        )
        frames = mnemosyne_facade.group_pulses(entries)
        if from_seq > 0:
            frames = mnemosyne_facade.discard_incomplete_frames(frames)
        report = mnemosyne_facade.validate_pulse_integrity(frames)
        min_seq = int(entries[0].get("seq", 0) or 0) if entries else 0
        max_seq = int(entries[-1].get("seq", 0) or 0) if entries else 0
        intents = []
        if max_seq > 0:
            try:
                intent_rows = mnemosyne_facade.fetch_intents_between(project_id, agent_id, max(1, min_seq), max_seq)
            except Exception:
                intent_rows = []
            for it in list(intent_rows or []):
                payload = dict(getattr(it, "payload", {}) or {})
                intents.append(
                    {
                        "intent_seq": int(getattr(it, "intent_seq", 0) or 0),
                        "intent_id": str(getattr(it, "intent_id", "") or ""),
                        "intent_key": str(getattr(it, "intent_key", "") or ""),
                        "source_kind": str(getattr(it, "source_kind", "") or ""),
                        "pulse_id": str(payload.get("pulse_id", "") or ""),
                        "timestamp": float(getattr(it, "timestamp", 0.0) or 0.0),
                        "fallback_text": str(getattr(it, "fallback_text", "") or ""),
                    }
                )
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "entries": entries,
            "pulses": [
                {
                    "pulse_id": fr.pulse_id,
                    "start": fr.start,
                    "triggers": fr.triggers,
                    "llm": fr.llm,
                    "tools": fr.tools,
                    "finish": fr.finish,
                }
                for fr in frames
            ],
            "intents": intents,
            "errors": report.errors,
            "warnings": report.warnings,
            "count": len(frames),
        }

    def outbox_receipts(
        self,
        project_id: str,
        from_agent_id: str = "",
        to_agent_id: str = "",
        status: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        self.ensure_exists(project_id)
        rows = iris_facade.list_outbox_receipts(
            project_id=project_id,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            status=status,
            limit=max(1, min(limit, 500)),
        )
        return {"project_id": project_id, "items": [r.to_dict() for r in rows]}

    def get_report(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        report = load_project_report(project_id)
        if not report:
            raise HTTPException(status_code=404, detail="Project report not found")
        return report


project_service = ProjectService()
