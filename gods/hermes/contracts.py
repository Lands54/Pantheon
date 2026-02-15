"""Hermes contract registry and resolution."""
from __future__ import annotations

import copy
import time
from typing import Any

from gods.hermes import store
from gods.hermes.errors import HermesError, HERMES_BAD_REQUEST
from gods.hermes.events import hermes_events


class HermesContracts:
    def register(self, project_id: str, contract: dict[str, Any]) -> dict[str, Any]:
        name = str(contract.get("name", "")).strip()
        version = str(contract.get("version", "")).strip()
        submitter = str(contract.get("submitter", "")).strip()
        if not name or not version or not submitter:
            raise HermesError(HERMES_BAD_REQUEST, "contract requires name/version/submitter")

        default_ob = contract.get("default_obligations", [])
        obligations = contract.get("obligations", {})
        committers = contract.get("committers", [])

        if not isinstance(default_ob, list) or not isinstance(obligations, dict) or not isinstance(committers, list):
            raise HermesError(HERMES_BAD_REQUEST, "invalid contract shape: default_obligations(list), obligations(dict), committers(list)")

        data = store.load_contracts(project_id)
        contracts = data.get("contracts", [])

        now = time.time()
        payload = {
            "name": name,
            "version": version,
            "submitter": submitter,
            "status": str(contract.get("status", "active") or "active"),
            "default_obligations": default_ob,
            "obligations": obligations,
            "committers": sorted(list({str(x).strip() for x in committers if str(x).strip()})),
            "created_at": now,
            "updated_at": now,
        }

        replaced = False
        for i, row in enumerate(contracts):
            if row.get("name") == name and row.get("version") == version:
                payload["created_at"] = row.get("created_at", now)
                contracts[i] = payload
                replaced = True
                break
        if not replaced:
            contracts.append(payload)

        data["contracts"] = contracts
        store.save_contracts(project_id, data)
        hermes_events.publish(
            "contract_registered",
            project_id,
            {"name": name, "version": version, "submitter": submitter, "committers": payload["committers"], "replaced": replaced},
        )
        return payload

    def get(self, project_id: str, name: str, version: str) -> dict[str, Any]:
        data = store.load_contracts(project_id)
        for row in data.get("contracts", []):
            if row.get("name") == name and row.get("version") == version:
                return row
        raise HermesError(HERMES_BAD_REQUEST, f"contract not found: {name}@{version}")

    def list(self, project_id: str) -> list[dict]:
        return store.load_contracts(project_id).get("contracts", [])

    def commit(self, project_id: str, name: str, version: str, agent_id: str) -> dict[str, Any]:
        agent_id = str(agent_id or "").strip()
        if not agent_id:
            raise HermesError(HERMES_BAD_REQUEST, "agent_id is required")
        data = store.load_contracts(project_id)
        contracts = data.get("contracts", [])
        found = None
        for i, row in enumerate(contracts):
            if row.get("name") == name and row.get("version") == version:
                found = (i, row)
                break
        if not found:
            raise HermesError(HERMES_BAD_REQUEST, f"contract not found: {name}@{version}")
        idx, row = found
        committers = set(row.get("committers", []))
        committers.add(agent_id)
        row["committers"] = sorted(committers)
        row["updated_at"] = time.time()
        contracts[idx] = row
        data["contracts"] = contracts
        store.save_contracts(project_id, data)
        hermes_events.publish(
            "contract_committed",
            project_id,
            {"name": name, "version": version, "agent_id": agent_id},
        )
        return row

    def resolve(self, project_id: str, name: str, version: str) -> dict[str, Any]:
        row = copy.deepcopy(self.get(project_id, name, version))
        default_ob = row.get("default_obligations", [])
        obligations = row.get("obligations", {})
        committers = row.get("committers", [])

        resolved: dict[str, list[dict]] = {}
        for agent in committers:
            own = obligations.get(agent)
            if isinstance(own, list) and own:
                resolved[agent] = own
            else:
                resolved[agent] = default_ob

        return {
            "name": row.get("name"),
            "version": row.get("version"),
            "submitter": row.get("submitter"),
            "status": row.get("status"),
            "committers": committers,
            "resolved_obligations": resolved,
        }
