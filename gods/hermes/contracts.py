"""Hermes contract registry and resolution."""
from __future__ import annotations

import copy
import re
import time
from typing import Any

from gods.hermes import store
from gods.hermes.errors import HermesError, HERMES_BAD_REQUEST
from gods.hermes.events import hermes_events
from gods.hermes.models import ProtocolSpec
from gods.hermes.registry import HermesRegistry
from gods.hermes.policy import allow_agent_tool_provider


class HermesContracts:
    """
    Registry and resolver for Hermes contracts, maintaining obligations and committers.
    """
    def __init__(self):
        self.registry = HermesRegistry()

    def _slug(self, text: str) -> str:
        v = re.sub(r"[^a-z0-9_]+", "_", (text or "").strip().lower())
        v = re.sub(r"_+", "_", v).strip("_")
        return v or "x"

    def _normalize_contract_ns(self, title: str) -> str:
        raw = (title or "").strip().lower()
        if re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", raw):
            return raw
        parts = [self._slug(x) for x in re.split(r"[^a-z0-9_]+", raw) if x.strip()]
        if len(parts) < 2:
            parts = ["contract", parts[0] if parts else "x"]
        return ".".join(parts)

    def _extract_io(self, clause: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        io = clause.get("io", {}) if isinstance(clause.get("io"), dict) else {}
        req = clause.get("request_schema") or io.get("request_schema") or {"type": "object"}
        resp = clause.get("response_schema") or io.get("response_schema") or {"type": "object"}
        if not isinstance(req, dict) or not isinstance(resp, dict):
            raise HermesError(HERMES_BAD_REQUEST, "clause request_schema/response_schema must be objects")
        return req, resp

    def _extract_runtime(self, clause: dict[str, Any]) -> dict[str, Any]:
        runtime = clause.get("runtime", {}) if isinstance(clause.get("runtime"), dict) else {}
        mode = str(runtime.get("mode", "both") or "both")
        if mode not in {"sync", "async", "both"}:
            raise HermesError(HERMES_BAD_REQUEST, f"invalid clause runtime.mode: {mode}")
        return {
            "mode": mode,
            "timeout_sec": int(runtime.get("timeout_sec", 30)),
            "rate_per_minute": int(runtime.get("rate_per_minute", 60)),
            "max_concurrency": int(runtime.get("max_concurrency", 2)),
        }

    def _extract_provider(self, project_id: str, clause: dict[str, Any], owner_agent: str) -> dict[str, Any]:
        provider = clause.get("provider")
        if not isinstance(provider, dict):
            raise HermesError(HERMES_BAD_REQUEST, "clause provider is required")
        ptype = str(provider.get("type", "")).strip()
        if ptype not in {"http", "agent_tool"}:
            raise HermesError(HERMES_BAD_REQUEST, "clause provider.type must be http|agent_tool")

        out = dict(provider)
        out["type"] = ptype
        out["project_id"] = project_id
        if ptype == "http":
            if not str(out.get("url", "")).strip():
                raise HermesError(HERMES_BAD_REQUEST, "http clause provider.url is required")
            out["method"] = str(out.get("method", "POST")).upper()
        else:
            if not allow_agent_tool_provider(project_id):
                raise HermesError(HERMES_BAD_REQUEST, "agent_tool provider is disabled by project policy")
            out["agent_id"] = str(out.get("agent_id") or owner_agent).strip()
            if not out["agent_id"]:
                raise HermesError(HERMES_BAD_REQUEST, "agent_tool clause provider.agent_id is required")
            if not str(out.get("tool_name", "")).strip():
                raise HermesError(HERMES_BAD_REQUEST, "agent_tool clause provider.tool_name is required")
        return out

    def _clause_to_protocol(
        self,
        project_id: str,
        contract_title: str,
        contract_version: str,
        clause: dict[str, Any],
        owner_override: str = "",
    ) -> ProtocolSpec:
        if not isinstance(clause, dict):
            raise HermesError(HERMES_BAD_REQUEST, "contract clause must be object")

        function_id = str(clause.get("function_id") or clause.get("id") or "").strip()
        if not function_id:
            raise HermesError(HERMES_BAD_REQUEST, "contract clause requires id or function_id")
        owner_agent = str(owner_override or clause.get("owner_agent") or "").strip()
        if not owner_agent:
            raise HermesError(HERMES_BAD_REQUEST, f"clause '{function_id}' requires owner_agent")

        runtime = self._extract_runtime(clause)
        provider = self._extract_provider(project_id, clause, owner_agent)
        req_schema, resp_schema = self._extract_io(clause)
        namespace = self._normalize_contract_ns(contract_title)
        action = self._slug(f"{owner_agent}_{function_id}")
        protocol_name = str(clause.get("protocol_name") or f"{namespace}.{action}").strip().lower()
        protocol_version = str(clause.get("protocol_version") or contract_version).strip()

        return ProtocolSpec(
            name=protocol_name,
            version=protocol_version,
            description=str(clause.get("summary") or clause.get("description") or "").strip(),
            mode=runtime["mode"],
            status="active",
            owner_agent=owner_agent,
            function_id=function_id,
            provider=provider,
            request_schema=req_schema,
            response_schema=resp_schema,
            limits={
                "timeout_sec": runtime["timeout_sec"],
                "rate_per_minute": runtime["rate_per_minute"],
                "max_concurrency": runtime["max_concurrency"],
            },
        )

    def _register_clauses(
        self,
        project_id: str,
        contract_title: str,
        contract_version: str,
        clauses: list[dict[str, Any]],
        owner_override: str = "",
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for clause in clauses:
            spec = self._clause_to_protocol(
                project_id=project_id,
                    contract_title=contract_title,
                contract_version=contract_version,
                clause=clause,
                owner_override=owner_override,
            )
            self.registry.register(project_id, spec)
            out.append(
                {
                    "name": spec.name,
                    "version": spec.version,
                    "owner_agent": spec.owner_agent,
                    "function_id": spec.function_id,
                }
            )
        return out

    def register(self, project_id: str, contract: dict[str, Any]) -> dict[str, Any]:
        """
        Registers or updates a contract specification in a project.
        """
        title = str(contract.get("title", "")).strip()
        version = str(contract.get("version", "")).strip()
        submitter = str(contract.get("submitter", "")).strip()
        description = str(contract.get("description", "")).strip()
        if not title or not version or not submitter:
            raise HermesError(HERMES_BAD_REQUEST, "contract requires title/version/submitter")
        if not description:
            raise HermesError(HERMES_BAD_REQUEST, "contract requires non-empty description")
        status = str(contract.get("status", "active") or "active").strip().lower()
        if status not in {"active", "disabled"}:
            raise HermesError(HERMES_BAD_REQUEST, "contract status must be active|disabled")

        default_ob = contract.get("default_obligations", [])
        obligations = contract.get("obligations", {})
        committers = contract.get("committers", [])

        if not isinstance(default_ob, list) or not isinstance(obligations, dict) or not isinstance(committers, list):
            raise HermesError(HERMES_BAD_REQUEST, "invalid contract shape: default_obligations(list), obligations(dict), committers(list)")
        if not default_ob and not any(isinstance(v, list) and v for v in obligations.values()):
            raise HermesError(HERMES_BAD_REQUEST, "contract must contain at least one executable clause")

        with store.contract_lock(project_id):
            data = store.load_contracts(project_id)
            contracts = data.get("contracts", [])

            now = time.time()
            committer_set = {str(x).strip() for x in committers if str(x).strip()}
            committer_set.add(submitter)
            payload = {
                "title": title,
                "version": version,
                "description": description,
                "submitter": submitter,
                "status": status,
                "default_obligations": default_ob,
                "obligations": obligations,
                "committers": sorted(list(committer_set)),
                "created_at": now,
                "updated_at": now,
            }

            replaced = False
            for i, row in enumerate(contracts):
                if row.get("title") == title and row.get("version") == version:
                    payload["created_at"] = row.get("created_at", now)
                    contracts[i] = payload
                    replaced = True
                    break
            if not replaced:
                contracts.append(payload)

            data["contracts"] = contracts
            store.save_contracts(project_id, data)

        # Contract-first: every clause is executable; sync clauses into protocol registry.
        registered_protocols: list[dict[str, Any]] = []
        for agent_id, clauses in obligations.items():
            if not isinstance(clauses, list):
                raise HermesError(HERMES_BAD_REQUEST, f"obligations.{agent_id} must be list")
            if status == "active":
                registered_protocols.extend(
                    self._register_clauses(
                        project_id=project_id,
                        contract_title=title,
                        contract_version=version,
                        clauses=clauses,
                        owner_override=str(agent_id),
                    )
                )

        # For current committers, materialize default obligations as executable clauses.
        if status == "active" and default_ob:
            for committer in payload["committers"]:
                registered_protocols.extend(
                    self._register_clauses(
                        project_id=project_id,
                        contract_title=title,
                        contract_version=version,
                        clauses=default_ob,
                        owner_override=committer,
                    )
                )

        hermes_events.publish(
            "contract_registered",
            project_id,
            {
                "title": title,
                "version": version,
                "description": description,
                "submitter": submitter,
                "committers": payload["committers"],
                "replaced": replaced,
                "registered_protocols": registered_protocols,
            },
        )
        payload["registered_protocols"] = registered_protocols
        return payload

    def get(self, project_id: str, title: str, version: str) -> dict[str, Any]:
        """
        Retrieves a specific contract by title and version.
        """
        data = store.load_contracts(project_id)
        for row in data.get("contracts", []):
            if row.get("title") == title and row.get("version") == version:
                return row
        raise HermesError(HERMES_BAD_REQUEST, f"contract not found: {title}@{version}")

    def list(self, project_id: str, include_disabled: bool = False) -> list[dict]:
        """
        Lists all contracts available in a project.
        """
        rows = store.load_contracts(project_id).get("contracts", [])
        if include_disabled:
            return rows
        return [r for r in rows if str(r.get("status", "active")) == "active"]

    def commit(self, project_id: str, title: str, version: str, agent_id: str) -> dict[str, Any]:
        """
        Allows an agent to commit to a specific contract.
        """
        agent_id = str(agent_id or "").strip()
        if not agent_id:
            raise HermesError(HERMES_BAD_REQUEST, "agent_id is required")
        with store.contract_lock(project_id):
            data = store.load_contracts(project_id)
            contracts = data.get("contracts", [])
            found = None
            for i, row in enumerate(contracts):
                if row.get("title") == title and row.get("version") == version:
                    found = (i, row)
                    break
            if not found:
                raise HermesError(HERMES_BAD_REQUEST, f"contract not found: {title}@{version}")
            idx, row = found
            if row.get("status", "active") != "active":
                raise HermesError(HERMES_BAD_REQUEST, "contract is disabled; commit is not allowed")
            committers = set(row.get("committers", []))
            committers.add(agent_id)
            row["committers"] = sorted(committers)
            row["updated_at"] = time.time()
            contracts[idx] = row
            data["contracts"] = contracts
            store.save_contracts(project_id, data)

        registered_protocols: list[dict[str, Any]] = []
        default_ob = row.get("default_obligations", [])
        if isinstance(default_ob, list) and default_ob:
            registered_protocols = self._register_clauses(
                project_id=project_id,
                contract_title=title,
                contract_version=version,
                clauses=default_ob,
                owner_override=agent_id,
            )

        hermes_events.publish(
            "contract_committed",
            project_id,
            {"title": title, "version": version, "agent_id": agent_id, "registered_protocols": registered_protocols},
        )
        row["registered_protocols"] = registered_protocols
        return row

    def disable(self, project_id: str, title: str, version: str, agent_id: str, reason: str = "") -> dict[str, Any]:
        """
        Exits caller from contract committers. Contract auto-disables when no committers remain.
        """
        agent_id = str(agent_id or "").strip()
        if not agent_id:
            raise HermesError(HERMES_BAD_REQUEST, "agent_id is required")

        with store.contract_lock(project_id):
            data = store.load_contracts(project_id)
            contracts = data.get("contracts", [])
            found = None
            for i, row in enumerate(contracts):
                if row.get("title") == title and row.get("version") == version:
                    found = (i, row)
                    break
            if not found:
                raise HermesError(HERMES_BAD_REQUEST, f"contract not found: {title}@{version}")

            idx, row = found
            committers = set(str(x).strip() for x in row.get("committers", []) if str(x).strip())
            if agent_id not in committers:
                raise HermesError(HERMES_BAD_REQUEST, f"agent '{agent_id}' is not a committer of this contract")

            committers.remove(agent_id)
            row["committers"] = sorted(committers)
            row["updated_at"] = time.time()
            row["last_disable_reason"] = str(reason or "").strip()
            row["last_disabled_by"] = agent_id
            if not row["committers"]:
                row["status"] = "disabled"
                namespace = f"{self._normalize_contract_ns(title)}."
                reg = store.load_registry(project_id)
                protocols = reg.get("protocols", [])
                now = time.time()
                changed = False
                for i, p in enumerate(protocols):
                    pname = str(p.get("name", ""))
                    if not pname.startswith(namespace):
                        continue
                    if str(p.get("version", "")) != version:
                        continue
                    if p.get("status") != "disabled":
                        p["status"] = "disabled"
                        p["updated_at"] = now
                        protocols[i] = p
                        changed = True
                if changed:
                    reg["protocols"] = protocols
                    store.save_registry(project_id, reg)
            contracts[idx] = row
            data["contracts"] = contracts
            store.save_contracts(project_id, data)

        hermes_events.publish(
            "contract_disable_requested",
            project_id,
            {
                "title": title,
                "version": version,
                "agent_id": agent_id,
                "reason": str(reason or "").strip(),
                "remaining_committers": row.get("committers", []),
                "status": row.get("status", "active"),
            },
        )
        return row

    def resolve(self, project_id: str, title: str, version: str) -> dict[str, Any]:
        """
        Resolves the effective obligations for all committers of a contract.
        """
        row = copy.deepcopy(self.get(project_id, title, version))
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

        out = {
            "title": row.get("title"),
            "version": row.get("version"),
            "description": row.get("description", ""),
            "submitter": row.get("submitter"),
            "status": row.get("status"),
            "committers": committers,
            "resolved_obligations": resolved,
            # Contract-first alias: obligation == executable clause.
            "resolved_clauses": resolved,
        }
        if row.get("status") == "disabled":
            out["warning"] = "contract is disabled"
        return out
