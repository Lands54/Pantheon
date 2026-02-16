"""Project-scoped port lease registry for local HTTP services."""
from __future__ import annotations

import socket
import threading
import time
from typing import Any

from . import store
from gods.hermes.errors import HermesError, HERMES_BAD_REQUEST


class HermesPortRegistry:
    def __init__(self):
        self._lock = threading.Lock()

    def _is_free(self, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", int(port)))
            return True
        except OSError:
            return False

    def list(self, project_id: str) -> list[dict[str, Any]]:
        data = store.load_ports(project_id)
        leases = data.get("leases", [])
        return sorted(leases, key=lambda x: int(x.get("port", 0)))

    def reserve(
        self,
        project_id: str,
        owner_id: str,
        preferred_port: int | None = None,
        min_port: int = 12000,
        max_port: int = 19999,
        note: str = "",
    ) -> dict[str, Any]:
        owner_id = (owner_id or "").strip()
        if not owner_id:
            raise HermesError(HERMES_BAD_REQUEST, "owner_id is required")
        if min_port < 1024 or max_port <= min_port:
            raise HermesError(HERMES_BAD_REQUEST, "invalid port range")

        with self._lock:
            data = store.load_ports(project_id)
            leases = data.get("leases", [])
            used = {int(x.get("port", 0)) for x in leases}

            # Reuse existing lease by same owner if still free and unique
            for row in leases:
                if row.get("owner_id") == owner_id:
                    p = int(row.get("port", 0))
                    if p and self._is_free(p):
                        return row

            def alloc(port: int) -> dict[str, Any]:
                now = time.time()
                row = {
                    "owner_id": owner_id,
                    "port": int(port),
                    "note": note,
                    "created_at": now,
                    "updated_at": now,
                }
                leases.append(row)
                data["leases"] = leases
                store.save_ports(project_id, data)
                return row

            if preferred_port is not None:
                p = int(preferred_port)
                if p < min_port or p > max_port:
                    raise HermesError(HERMES_BAD_REQUEST, f"preferred_port out of range: {p}")
                if p in used:
                    raise HermesError("HERMES_PORT_IN_USE", f"preferred_port already leased: {p}", retryable=True)
                if not self._is_free(p):
                    raise HermesError("HERMES_PORT_BUSY", f"preferred_port not available on host: {p}", retryable=True)
                return alloc(p)

            for p in range(int(min_port), int(max_port) + 1):
                if p in used:
                    continue
                if not self._is_free(p):
                    continue
                return alloc(p)

            raise HermesError("HERMES_NO_FREE_PORT", "no free port available in configured range", retryable=True)

    def release(self, project_id: str, owner_id: str, port: int | None = None) -> int:
        owner_id = (owner_id or "").strip()
        if not owner_id:
            raise HermesError(HERMES_BAD_REQUEST, "owner_id is required")
        with self._lock:
            data = store.load_ports(project_id)
            leases = data.get("leases", [])
            kept = []
            removed = 0
            for row in leases:
                row_owner = str(row.get("owner_id", "")).strip()
                row_port = int(row.get("port", 0) or 0)
                matched = row_owner == owner_id and (port is None or row_port == int(port))
                if matched:
                    removed += 1
                else:
                    kept.append(row)
            data["leases"] = kept
            store.save_ports(project_id, data)
            return removed
