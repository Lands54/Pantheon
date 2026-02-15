"""Project lifecycle/report use-case service."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from gods.config import ProjectConfig, runtime_config
from gods.project.reporting import build_project_report, load_project_report
from gods.protocols import build_knowledge_graph


class ProjectService:
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
        agent_md = agent_dir / "agent.md"
        if not agent_md.exists():
            agent_md.write_text(
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
        # Single-active-project runtime policy: starting one project pauses all others.
        for pid, proj in runtime_config.projects.items():
            proj.simulation_enabled = pid == project_id

        runtime_config.current_project = project_id
        runtime_config.save()
        return {
            "status": "success",
            "project_id": project_id,
            "simulation_enabled": True,
            "current_project": runtime_config.current_project,
        }

    def stop_project(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        runtime_config.projects[project_id].simulation_enabled = False
        runtime_config.save()
        return {
            "status": "success",
            "project_id": project_id,
            "simulation_enabled": False,
            "current_project": runtime_config.current_project,
        }

    def build_report(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        # Report builder also archives markdown into Mnemosyne human vault.
        report = build_project_report(project_id)
        return {
            "status": "success",
            "project_id": project_id,
            "protocol_count": report.get("protocol_count", 0),
            "invocation_count": report.get("invocation_count", 0),
            "top_protocols": report.get("top_protocols", []),
            "output": report.get("output", {}),
            "mnemosyne_entry_id": report.get("mnemosyne_entry_id", ""),
        }

    def get_report(self, project_id: str) -> dict[str, Any]:
        self.ensure_exists(project_id)
        report = load_project_report(project_id)
        if not report:
            raise HTTPException(status_code=404, detail="Project report not found")
        return report


project_service = ProjectService()
