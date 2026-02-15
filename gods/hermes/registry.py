"""Hermes protocol registry service."""
from __future__ import annotations

import time
from typing import Optional

from gods.hermes.errors import HermesError, HERMES_PROTOCOL_NOT_FOUND, HERMES_BAD_REQUEST
from gods.hermes.models import ProtocolSpec
from gods.hermes import store
from gods.hermes.events import hermes_events


class HermesRegistry:
    """
    Service for managing the registration and retrieval of Hermes protocol specifications.
    """
    def register(self, project_id: str, spec: ProtocolSpec) -> ProtocolSpec:
        """
        Registers or updates a protocol specification in the registry.
        """
        if not project_id.strip():
            raise HermesError(HERMES_BAD_REQUEST, "project_id is required")
        now = time.time()
        data = store.load_registry(project_id)
        protocols = data.get("protocols", [])

        replaced = False
        for i, row in enumerate(protocols):
            if row.get("name") == spec.name:
                existing = ProtocolSpec(**row)
                merged = spec.model_copy(update={"created_at": existing.created_at, "updated_at": now})
                protocols[i] = merged.model_dump()
                replaced = True
                break

        if not replaced:
            fresh = spec.model_copy(update={"created_at": now, "updated_at": now})
            protocols.append(fresh.model_dump())

        data["protocols"] = protocols
        store.save_registry(project_id, data)
        hermes_events.publish(
            "protocol_registered",
            project_id,
            {
                "name": spec.name,
                "provider": spec.provider.model_dump(),
                "replaced": replaced,
            },
        )
        return spec

    def list(self, project_id: str) -> list[ProtocolSpec]:
        """
        Lists all protocol specifications registered in a project.
        """
        data = store.load_registry(project_id)
        out = []
        for row in data.get("protocols", []):
            try:
                out.append(ProtocolSpec(**row))
            except Exception:
                continue
        return out

    def get(self, project_id: str, name: str) -> ProtocolSpec:
        """
        Retrieves a specific protocol specification by name.
        """
        for spec in self.list(project_id):
            if spec.name == name:
                return spec
        raise HermesError(
            HERMES_PROTOCOL_NOT_FOUND,
            f"Protocol not found: {name} in project '{project_id}'",
        )

    def delete(self, project_id: str, name: str) -> bool:
        """
        Deletes a protocol specification from the registry.
        """
        data = store.load_registry(project_id)
        protocols = data.get("protocols", [])
        filtered = [p for p in protocols if p.get("name") != name]
        if len(filtered) == len(protocols):
            return False
        data["protocols"] = filtered
        store.save_registry(project_id, data)
        return True
