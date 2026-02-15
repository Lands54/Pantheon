"""Hermes protocol registry service."""
from __future__ import annotations

import json
import hashlib
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
    def _content_fingerprint(self, spec: ProtocolSpec) -> str:
        payload = {
            "name": spec.name,
            "mode": spec.mode,
            "owner_agent": spec.owner_agent,
            "function_id": spec.function_id,
            "provider": spec.provider.model_dump(),
            "request_schema": spec.request_schema,
            "response_schema": spec.response_schema,
            "limits": spec.limits.model_dump(),
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

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
        auto_disabled_versions: list[str] = []
        new_fp = self._content_fingerprint(spec)
        for i, row in enumerate(protocols):
            if row.get("name") == spec.name and row.get("version") == spec.version:
                existing = ProtocolSpec(**row)
                existing_fp = self._content_fingerprint(existing)
                if existing_fp != new_fp:
                    raise HermesError(
                        HERMES_BAD_REQUEST,
                        f"Protocol content conflict for {spec.name}@{spec.version}: same version must keep identical executable content.",
                    )
                merged = spec.model_copy(update={"created_at": existing.created_at, "updated_at": now})
                protocols[i] = merged.model_dump()
                replaced = True
                break

        if not replaced:
            fresh = spec.model_copy(update={"created_at": now, "updated_at": now})
            protocols.append(fresh.model_dump())

        # Enforce single active version per protocol name.
        if spec.status == "active":
            for i, row in enumerate(protocols):
                if row.get("name") != spec.name:
                    continue
                if row.get("version") == spec.version:
                    continue
                if row.get("status") == "active":
                    row["status"] = "disabled"
                    row["updated_at"] = now
                    protocols[i] = row
                    auto_disabled_versions.append(str(row.get("version", "")))

        data["protocols"] = protocols
        store.save_registry(project_id, data)
        hermes_events.publish(
            "protocol_registered",
            project_id,
            {
                "name": spec.name,
                "version": spec.version,
                "provider": spec.provider.model_dump(),
                "replaced": replaced,
                "auto_disabled_versions": auto_disabled_versions,
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

    def get(self, project_id: str, name: str, version: str) -> ProtocolSpec:
        """
        Retrieves a specific protocol specification by name and version.
        """
        for spec in self.list(project_id):
            if spec.name == name and spec.version == version:
                return spec
        raise HermesError(
            HERMES_PROTOCOL_NOT_FOUND,
            f"Protocol not found: {name}@{version} in project '{project_id}'",
        )

    def delete(self, project_id: str, name: str, version: str) -> bool:
        """
        Deletes a protocol specification from the registry.
        """
        data = store.load_registry(project_id)
        protocols = data.get("protocols", [])
        filtered = [p for p in protocols if not (p.get("name") == name and p.get("version") == version)]
        if len(filtered) == len(protocols):
            return False
        data["protocols"] = filtered
        store.save_registry(project_id, data)
        return True
