"""Project lifecycle/report use-case service."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from gods.config import ProjectConfig, runtime_config
from gods.project.reporting import build_project_report, load_project_report
from gods.protocols import build_knowledge_graph
from gods.runtime.detach import DetachError, get_logs as detach_get_logs, list_for_api as detach_list_for_api
from gods.runtime.detach import reconcile as detach_reconcile
from gods.runtime.detach import stop as detach_stop
from gods.runtime.detach import submit as detach_submit
from gods.runtime.docker import DockerRuntimeManager
from gods.janus import janus_service


class ProjectService:
    def __init__(self):
        self._docker = DockerRuntimeManager()

    def list_projects(self) -> dict[str, Any]:
        return {"projects": runtime_config.projects, "current": runtime_config.current_project}

    def create_project(self, pid: str) -> dict[str, str]:
        if not pid:
            raise HTTPException(status_code=400, detail="Project id is required")
        if pid in runtime_config.projects:
            return {"error": "Project exists"}

        runtime_config.projects[pid] = ProjectConfig()
        runtime_config.save()

        agent_dir = Path("projects") / pid / "agents" / "genesis"
        agent_dir.mkdir(parents=True, exist_ok=True)
        profile = Path("projects") / pid / "mnemosyne" / "agent_profiles" / "genesis.md"
        if not profile.exists():
            profile.parent.mkdir(parents=True, exist_ok=True)
            profile.write_text(
                "# GENESIS\nYou are the first Being of this new world. Observe, evolve, and manifest.",
                encoding="utf-8",
            )
        return {"status": "success"}

    def delete_project(self, project_id: str) -> dict[str, str]:
        if project_id == "default":
            raise HTTPException(status_code=400, detail="Cannot delete default world")
        if project_id not in runtime_config.projects:
            raise HTTPException(status_code=404, detail="Project not found")

        del runtime_config.projects[project_id]
        if runtime_config.current_project == project_id:
            runtime_config.current_project = "default"
        runtime_config.save()

        proj_dir = Path("projects") / project_id
        if proj_dir.exists():
            shutil.rmtree(proj_dir)
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
            ok, msg = self._docker.docker_available()
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
                ok, msg = self._docker.docker_available()
                runtime_info = {"enabled": True, "available": ok, "detail": msg, "ensured": []}
                if ok:
                    for aid in proj.active_agents:
                        try:
                            st = self._docker.ensure_agent_runtime(project_id, aid)
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
                    self._docker.stop_agent_runtime(project_id, aid)
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
        rows = self._docker.list_project_runtimes(project_id, proj.active_agents)
        ok, msg = self._docker.docker_available()
        return {"project_id": project_id, "docker_available": ok, "docker_detail": msg, "agents": rows}

    def runtime_restart_agent(self, project_id: str, agent_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        proj = runtime_config.projects[project_id]
        if agent_id not in proj.active_agents:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' is not active in project '{project_id}'")
        ok, msg = self._docker.docker_available()
        if not ok:
            raise HTTPException(status_code=503, detail=f"Docker unavailable: {msg}")
        st = self._docker.restart_agent_runtime(project_id, agent_id)
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
        ok, msg = self._docker.docker_available()
        if not ok:
            raise HTTPException(status_code=503, detail=f"Docker unavailable: {msg}")
        return self._docker.reconcile_project(project_id, proj.active_agents)

    def detach_submit(self, project_id: str, agent_id: str, command: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        try:
            return detach_submit(project_id=project_id, agent_id=agent_id, command=command)
        except DetachError as e:
            raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}") from e

    def detach_list(self, project_id: str, agent_id: str, status: str, limit: int) -> dict[str, Any]:
        self.ensure_exists(project_id)
        try:
            return detach_list_for_api(project_id=project_id, agent_id=agent_id, status=status, limit=limit)
        except DetachError as e:
            raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}") from e

    def detach_stop(self, project_id: str, job_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        try:
            return detach_stop(project_id=project_id, job_id=job_id, reason="manual")
        except DetachError as e:
            raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}") from e

    def detach_reconcile(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        try:
            return detach_reconcile(project_id=project_id)
        except DetachError as e:
            raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}") from e

    def detach_logs(self, project_id: str, job_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        try:
            return detach_get_logs(project_id=project_id, job_id=job_id)
        except DetachError as e:
            raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}") from e

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
        row = janus_service.context_preview(project_id, agent_id)
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "preview": row,
        }

    def context_reports(self, project_id: str, agent_id: str, limit: int) -> dict[str, Any]:
        self.ensure_exists(project_id)
        rows = janus_service.context_reports(project_id, agent_id, limit=max(1, min(limit, 500)))
        return {
            "project_id": project_id,
            "agent_id": agent_id,
            "reports": rows,
        }

    def get_report(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        report = load_project_report(project_id)
        if not report:
            raise HTTPException(status_code=404, detail="Project report not found")
        return report


project_service = ProjectService()
