"""Hermes contract registry and resolution."""
from __future__ import annotations

import copy
import re
import time
from typing import Any

from . import store
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

    def _required_committers(self, row: dict[str, Any]) -> list[str]:
        required = {str(row.get("submitter", "")).strip()}
        required.update(str(x).strip() for x in row.get("proposed_committers", []) if str(x).strip())
        return sorted(x for x in required if x)

    def _commit_snapshot(self, row: dict[str, Any]) -> dict[str, Any]:
        required = self._required_committers(row)
        committed = sorted(str(x).strip() for x in row.get("committers", []) if str(x).strip())
        committed_set = set(committed)
        missing = [x for x in required if x not in committed_set]
        return {
            "required_committers": required,
            "committed_committers": committed,
            "missing_committers": missing,
            "required_count": len(required),
            "committed_count": len(committed),
            "missing_count": len(missing),
            "is_fully_committed": len(missing) == 0,
        }

    def _attach_commit_snapshot(self, row: dict[str, Any]) -> dict[str, Any]:
        out = copy.deepcopy(row)
        out.update(self._commit_snapshot(out))
        return out

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
        _ = contract_version  # reserved for contract lifecycle only; protocols are versionless.

        return ProtocolSpec(
            name=protocol_name,
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
            # Common mistake: submit descriptive obligations (functions/commitments) instead of executable clauses.
            if any(isinstance(v, dict) and ("functions" in v or "commitments" in v) for v in obligations.values()):
                raise HermesError(
                    HERMES_BAD_REQUEST,
                    "contract obligations are descriptive, not executable. Use list clauses with provider/io/runtime, e.g. obligations.agent=[{id,provider,io,runtime}]",
                )
            raise HermesError(HERMES_BAD_REQUEST, "contract must contain at least one executable clause")

        with store.contract_lock(project_id):
            data = store.load_contracts(project_id)
            contracts = data.get("contracts", [])

            now = time.time()
            proposed_committers = sorted(list({str(x).strip() for x in committers if str(x).strip()}))
            payload = {
                "title": title,
                "version": version,
                "description": description,
                "submitter": submitter,
                "status": status,
                "default_obligations": default_ob,
                "obligations": obligations,
                # Registration stage only commits submitter.
                "committers": [submitter],
                # Keep proposal intent for observability, but does not auto-join anyone.
                "proposed_committers": proposed_committers,
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
        return self._attach_commit_snapshot(payload)

    def get(self, project_id: str, title: str, version: str) -> dict[str, Any]:
        """
        Retrieves a specific contract by title and version.
        """
        data = store.load_contracts(project_id)
        for row in data.get("contracts", []):
            if row.get("title") == title and row.get("version") == version:
                return self._attach_commit_snapshot(row)
        raise HermesError(HERMES_BAD_REQUEST, f"contract not found: {title}@{version}")

    def list(self, project_id: str, include_disabled: bool = False) -> list[dict]:
        """
        Lists all contracts available in a project.
        """
        rows = store.load_contracts(project_id).get("contracts", [])
        rows = [self._attach_commit_snapshot(r) for r in rows]
        if include_disabled:
            return rows
        return [r for r in rows if str(r.get("status", "active")) == "active"]

    def _notify_committers(self, project_id: str, title: str, version: str, committer: str, targets: list[str]) -> list[str]:
        """
        Notify existing committers that a new agent has committed.
        Best-effort: notification failures should not break commit path.
        """
        sent: list[str] = []
        targets = [str(x).strip() for x in (targets or []) if str(x).strip() and str(x).strip() != committer]
        if not targets:
            return sent

        try:
            from gods.iris import enqueue_message
            from gods.angelia.pulse import get_priority_weights, is_inbox_event_enabled
        except Exception:
            return sent

        trigger = bool(is_inbox_event_enabled(project_id))
        weights = get_priority_weights(project_id)
        priority = int(weights.get("inbox_event", 100))
        msg = (
            f"Hermes Notice: agent '{committer}' committed contract "
            f"'{title}@{version}'."
        )
        for aid in targets:
            try:
                enqueue_message(
                    project_id=project_id,
                    agent_id=aid,
                    sender="Hermes",
                    title="Contract Commit Notice",
                    content=msg,
                    msg_type="contract_notice",
                    trigger_pulse=trigger,
                    pulse_priority=priority,
                )
                sent.append(aid)
            except Exception:
                continue
        return sent

    def _notify_fully_committed(self, project_id: str, title: str, version: str, targets: list[str]) -> list[str]:
        """
        Notify all committers when a contract becomes fully committed.
        Best-effort: notification failures should not break commit path.
        """
        sent: list[str] = []
        targets = [str(x).strip() for x in (targets or []) if str(x).strip()]
        if not targets:
            return sent

        try:
            from gods.iris import enqueue_message
            from gods.angelia.pulse import get_priority_weights, is_inbox_event_enabled
        except Exception:
            return sent

        trigger = bool(is_inbox_event_enabled(project_id))
        weights = get_priority_weights(project_id)
        priority = int(weights.get("inbox_event", 100))
        msg = (
            f"Hermes Notice: contract '{title}@{version}' is now fully committed "
            f"by all required committers."
        )
        for aid in targets:
            try:
                enqueue_message(
                    project_id=project_id,
                    agent_id=aid,
                    sender="Hermes",
                    title="Contract Fully Committed",
                    content=msg,
                    msg_type="contract_fully_committed",
                    trigger_pulse=trigger,
                    pulse_priority=priority,
                )
                sent.append(aid)
            except Exception:
                continue
        return sent

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
            required = set(self._required_committers(row))
            if agent_id not in required:
                raise HermesError(
                    HERMES_BAD_REQUEST,
                    f"agent '{agent_id}' is not allowed to commit this contract",
                )
            before = self._commit_snapshot(row)
            committers = set(str(x).strip() for x in row.get("committers", []) if str(x).strip())
            committers.add(agent_id)
            row["committers"] = sorted(committers)
            row["updated_at"] = time.time()
            after = self._commit_snapshot(row)
            if after["is_fully_committed"] and not before["is_fully_committed"]:
                row["activated_at"] = time.time()
            contracts[idx] = row
            data["contracts"] = contracts
            store.save_contracts(project_id, data)

        registered_protocols: list[dict[str, Any]] = []
        notified_agents: list[str] = self._notify_committers(
            project_id=project_id,
            title=title,
            version=version,
            committer=agent_id,
            targets=list(before.get("committed_committers", []) or []),
        )
        notified_fully_agents: list[str] = []
        after_snapshot = self._commit_snapshot(row)
        if bool(after_snapshot.get("is_fully_committed")) and (not bool(before.get("is_fully_committed"))):
            notified_fully_agents = self._notify_fully_committed(
                project_id=project_id,
                title=title,
                version=version,
                targets=list(after_snapshot.get("committed_committers", []) or []),
            )
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
            {
                "title": title,
                "version": version,
                "agent_id": agent_id,
                "registered_protocols": registered_protocols,
                "notified_agents": notified_agents,
                "notified_fully_agents": notified_fully_agents,
                "commit_snapshot": after_snapshot,
            },
        )
        row["registered_protocols"] = registered_protocols
        row["notified_agents"] = notified_agents
        row["notified_fully_agents"] = notified_fully_agents
        return self._attach_commit_snapshot(row)

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
        return self._attach_commit_snapshot(row)
