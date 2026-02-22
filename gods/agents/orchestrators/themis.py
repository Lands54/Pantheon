"""Themis orchestrator: tool policy resolution and execution."""
from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Any, Callable

from gods.agents.runtime_policy import resolve_phase_strategy
from gods.config import runtime_config
from gods.mnemosyne.facade import append_pulse_entry
from gods.mnemosyne.intent_builders import intent_from_tool_call, intent_from_tool_result
from gods.tools import GODS_TOOLS
from gods.tools.communication import reset_inbox_guard

logger = logging.getLogger(__name__)


class ThemisOrchestrator:
    def __init__(
        self,
        *,
        project_id: str,
        agent_id: str,
        agent_dir: Path,
        tools_provider: Callable[[], list[Any]] | None = None,
        intent_recorder: Callable[[Any], Any] | None = None,

    ):
        self.project_id = project_id
        self.agent_id = agent_id
        self.agent_dir = agent_dir
        self._tools_provider = tools_provider or (lambda: GODS_TOOLS)
        self._intent_recorder = intent_recorder or (lambda _intent: None)


    @staticmethod
    def _normalize_allowlist(raw: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in list(raw or []):
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(name)
        return out

    @staticmethod
    def classify_tool_status(result: str) -> str:
        text = str(result or "").strip()
        norm = re.sub(r"^\[Current CWD:[^\]]+\]\s*", "", text, flags=re.I).strip()
        if norm.lower().startswith("content:"):
            norm = norm[len("content:") :].strip()
        low = norm.lower()

        if "divine restriction" in low or "policy block" in low:
            return "blocked"

        error_prefixes = (
            "tool execution error:",
            "tool error:",
            "path error:",
            "execution failed:",
            "execution timeout:",
            "execution backend error:",
            "territory error:",
            "command error:",
            "concurrency limit:",
        )
        if low.startswith(error_prefixes):
            return "error"

        m = re.search(r"manifestation result \(exit=(-?\d+)\):", low)
        if m:
            try:
                return "ok" if int(m.group(1)) == 0 else "error"
            except Exception:
                return "error"

        return "ok"

    @staticmethod
    def finalize_control_from_args(args: dict) -> dict:
        raw = dict(args or {})
        mode = str(raw.get("mode", "done") or "done").strip().lower()
        if mode not in {"done", "quiescent"}:
            mode = "done"
        try:
            sleep_sec = int(raw.get("sleep_sec", 0) or 0)
        except Exception:
            sleep_sec = 0
        return {
            "mode": mode,
            "sleep_sec": sleep_sec,
            "reason": str(raw.get("reason", "") or ""),
        }

    def _resolve_node_tool_allowlist(self, node_name: str) -> list[str] | None:
        phase = str(node_name or "").strip().lower() or "global"
        proj = runtime_config.projects.get(self.project_id)
        if not proj:
            return None
        strategy = resolve_phase_strategy(self.project_id, self.agent_id)

        def _from_tool_policies(scope_obj) -> list[str] | None:
            policies = getattr(scope_obj, "tool_policies", None)
            if not isinstance(policies, dict):
                return None
            strategy_map = policies.get(strategy)
            if not isinstance(strategy_map, dict):
                return None
            if phase in strategy_map and isinstance(strategy_map.get(phase), list):
                return self._normalize_allowlist(list(strategy_map.get(phase) or []))
            if "global" in strategy_map and isinstance(strategy_map.get("global"), list):
                return self._normalize_allowlist(list(strategy_map.get("global") or []))
            return None

        agent_cfg = proj.agent_settings.get(self.agent_id) if proj else None
        if agent_cfg:
            allow = _from_tool_policies(agent_cfg)
            if allow is not None:
                return allow
        allow = _from_tool_policies(proj)
        if allow is not None:
            return allow
        return None

    def _is_tool_allowed_for_node(self, tool_name: str, node_name: str) -> bool:
        allow = self._resolve_node_tool_allowlist(node_name)
        if allow is None:
            return True
        return str(tool_name or "").strip() in set(allow)

    def get_tools(self) -> list[Any]:
        disabled: set[str] = set()
        proj = runtime_config.projects.get(self.project_id)
        if proj:
            settings = proj.agent_settings.get(self.agent_id)
            if settings:
                disabled = set(settings.disabled_tools or [])
        return [t for t in self._tools_provider() if t.name not in disabled]

    def get_tools_for_node(self, node_name: str) -> list[Any]:
        base = self.get_tools()
        allow = self._resolve_node_tool_allowlist(node_name)
        if allow is None:
            return base
        allow_set = set(allow)
        return [t for t in base if t.name in allow_set]

    def render_tools_desc(self, node_name: str = "llm_think") -> str:
        items = []
        for t in self.get_tools_for_node(node_name):
            desc = str(getattr(t, "description", "") or "")
            if str(getattr(t, "name", "") or "") == "council_action":
                try:
                    from gods.angelia import sync_council as council_sync

                    win = council_sync.action_window(self.project_id, self.agent_id) or {}
                    allowed = list(win.get("allowed_actions", []) or [])
                    if allowed:
                        desc = f"{desc} Current allowed_actions: {', '.join(allowed)}."
                except Exception:
                    pass
            items.append(f"- [[{t.name}({', '.join(t.args)})]]: {desc}")
        return "\n".join(items)

    def execute_tool(self, name: str, args: dict, node_name: str = "", pulse_id: str = "") -> str:
        path_aware_tools = {
            "read",
            "write_file",
            "replace_content",
            "insert_content",
            "multi_replace",
            "list",
            "run_command",
        }

        def ensure_cwd_prefix(msg: str) -> str:
            if not isinstance(msg, str):
                return str(msg)
            if "[Current CWD:" in msg:
                return msg
            return f"[Current CWD: {self.agent_dir.resolve()}] Content: {msg}"

        def append_ledger(kind: str, payload: dict[str, Any]) -> None:
            pid = str(pulse_id or "").strip()
            if not pid:
                logger.warning(
                    "PULSE_LEDGER_SKIP: %s skipped because pulse_id is empty "
                    "(agent=%s, tool=%s)",
                    kind, self.agent_id, name,
                )
                return
            try:
                append_pulse_entry(
                    self.project_id,
                    self.agent_id,
                    pulse_id=pid,
                    kind=kind,  # type: ignore[arg-type]
                    payload=payload,
                    origin="internal",
                )
            except Exception as exc:
                logger.warning(
                    "PULSE_LEDGER_WRITE_FAIL: %s write failed "
                    "(agent=%s, pulse_id=%s): %s",
                    kind, self.agent_id, pid, exc,
                )

        invoke_args = dict(args or {})
        invoke_args["caller_id"] = self.agent_id
        invoke_args["project_id"] = self.project_id
        call_id = f"call_{uuid.uuid4().hex[:16]}"
        append_ledger(
            "tool.call",
            {
                "tool_name": str(name or ""),
                "args": dict(invoke_args or {}),
                "call_id": call_id,
                "node": str(node_name or "dispatch_tools"),
            },
        )
        self._intent_recorder(
            intent_from_tool_call(
                project_id=self.project_id,
                agent_id=self.agent_id,
                tool_name=name,
                args=invoke_args,
                node_name=node_name or "dispatch_tools",
                call_id=call_id,
                pulse_id=str(pulse_id or ""),
                origin="internal",
            )
        )

        proj = runtime_config.projects.get(self.project_id)
        if proj:
            settings = proj.agent_settings.get(self.agent_id)
            if settings and name in settings.disabled_tools:
                blocked = (
                    f"Divine Restriction: The tool '{name}' has been disabled for you by the High Overseer.\n"
                    "Suggested next step: choose another available tool aligned with your current phase."
                )

                self._intent_recorder(
                    intent_from_tool_result(
                        self.project_id,
                        self.agent_id,
                        name,
                        "blocked",
                        invoke_args,
                        blocked,
                        call_id=call_id,
                        pulse_id=str(pulse_id or ""),
                        origin="internal",
                    )
                )
                append_ledger(
                    "tool.result",
                    {
                        "tool_name": str(name or ""),
                        "status": "blocked",
                        "args": dict(invoke_args or {}),
                        "result": str(blocked),
                        "call_id": call_id,
                    },
                )
                return blocked

        if node_name and not self._is_tool_allowed_for_node(name, node_name):
            blocked = (
                f"Divine Restriction: The tool '{name}' is not allowed in node '{node_name}'.\n"
                "Suggested next step: choose a tool permitted by current node policy."
            )

            self._intent_recorder(
                intent_from_tool_result(
                    self.project_id,
                    self.agent_id,
                    name,
                    "blocked",
                    invoke_args,
                    blocked,
                    call_id=call_id,
                    pulse_id=str(pulse_id or ""),
                    origin="internal",
                )
            )
            append_ledger(
                "tool.result",
                {
                    "tool_name": str(name or ""),
                    "status": "blocked",
                    "args": dict(invoke_args or {}),
                    "result": str(blocked),
                    "call_id": call_id,
                },
            )
            return blocked
        for tool_func in self.get_tools_for_node(node_name or "dispatch_tools"):
            if tool_func.name != name:
                continue
            try:
                result = tool_func.invoke(invoke_args)
                if name in path_aware_tools:
                    result = ensure_cwd_prefix(result)
                if name != "check_inbox":
                    reset_inbox_guard(self.agent_id, self.project_id)
                status = self.classify_tool_status(str(result))

                self._intent_recorder(
                    intent_from_tool_result(
                        self.project_id,
                        self.agent_id,
                        name,
                        status,
                        invoke_args,
                        str(result),
                        call_id=call_id,
                        pulse_id=str(pulse_id or ""),
                        origin="internal",
                    )
                )
                append_ledger(
                    "tool.result",
                    {
                        "tool_name": str(name or ""),
                        "status": str(status or ""),
                        "args": dict(invoke_args or {}),
                        "result": str(result),
                        "call_id": call_id,
                    },
                )
                return str(result)
            except Exception as e:
                err = (
                    f"Tool Execution Error: failed to run '{name}'. Reason: {str(e)}\n"
                    "Suggested next step: verify required arguments and retry once."
                )

                self._intent_recorder(
                    intent_from_tool_result(
                        self.project_id,
                        self.agent_id,
                        name,
                        "error",
                        invoke_args,
                        err,
                        call_id=call_id,
                        pulse_id=str(pulse_id or ""),
                        origin="internal",
                    )
                )
                append_ledger(
                    "tool.result",
                    {
                        "tool_name": str(name or ""),
                        "status": "error",
                        "args": dict(invoke_args or {}),
                        "result": str(err),
                        "call_id": call_id,
                    },
                )
                return err

        available = ", ".join([t.name for t in self.get_tools_for_node(node_name or "dispatch_tools")])
        unknown = (
            f"Tool Error: Unknown tool '{name}'.\n"
            f"Suggested next step: choose one from [{available}]."
        )

        self._intent_recorder(
            intent_from_tool_result(
                self.project_id,
                self.agent_id,
                name,
                "error",
                invoke_args,
                unknown,
                call_id=call_id,
                pulse_id=str(pulse_id or ""),
                origin="internal",
            )
        )
        append_ledger(
            "tool.result",
            {
                "tool_name": str(name or ""),
                "status": "error",
                "args": dict(invoke_args or {}),
                "result": str(unknown),
                "call_id": call_id,
            },
        )
        return unknown
