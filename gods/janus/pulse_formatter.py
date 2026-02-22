"""Render sequential_v1 context into tagged static blocks and pulse frames."""
from __future__ import annotations

import json
import re
from collections import OrderedDict
import xml.etree.ElementTree as ET

from gods.janus.pulse_contract import (
    PulseAgentResponse,
    PulseAgentResponseSegment,
    PulseFrame,
    PulseToolCallItem,
    PulseTriggerItem,
    XmlIntentAtom,
)


def _clean_material_text(text: str, header: str) -> str:
    raw = str(text or "")
    p = f"[{header}]\n"
    if raw.startswith(p):
        return raw[len(p) :].strip()
    return raw.strip()


def _json_text(v: object) -> str:
    if isinstance(v, str):
        return v
    try:
        return json.dumps(v, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(v)


def _summary(text: str, max_len: int = 320) -> str:
    s = str(text or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


_CWD_PREFIX_RE = re.compile(r"^\[Current CWD:[^\]]*\]\s*Content:\s*", re.IGNORECASE)
_NOISE_LINE_RE = re.compile(
    r"^\s*(created_at|updated_at|timestamp|resolved_path|line_range|total_lines)\s*:\s*.*$",
    re.IGNORECASE,
)


def _clean_context_payload_text(value: object) -> str:
    s = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    if not s:
        return ""
    s = _CWD_PREFIX_RE.sub("", s)
    if "\n---\n" in s:
        head, body = s.split("\n---\n", 1)
        first = (head.splitlines() or [""])[0].strip()
        body_lines = [ln for ln in body.splitlines() if not _NOISE_LINE_RE.match(ln.strip())]
        body_clean = "\n".join(body_lines).strip()
        if first.startswith("[READ"):
            s = f"{first}\n{body_clean}".strip()
        else:
            s = body_clean
    else:
        lines = [ln for ln in s.splitlines() if not _NOISE_LINE_RE.match(ln.strip())]
        s = "\n".join(lines)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def _sanitize_tool_args(args: dict[str, object]) -> dict[str, object]:
    clean = dict(args or {})
    for k in ("caller_id", "agent_id", "project_id", "from_agent_id", "to_agent_id"):
        clean.pop(k, None)
    return clean


def _xml_safe_text(value: object) -> str:
    s = str(value or "")
    if not s:
        return ""
    out: list[str] = []
    for ch in s:
        cp = ord(ch)
        if ch in ("\t", "\n", "\r") or (0x20 <= cp <= 0xD7FF) or (0xE000 <= cp <= 0xFFFD) or (0x10000 <= cp <= 0x10FFFF):
            out.append(ch)
    return "".join(out)


def _frame_for(frames: OrderedDict[str, PulseFrame], pulse_id: str, ts: float) -> PulseFrame:
    pid = str(pulse_id or "").strip() or "pulse_unknown"
    row = frames.get(pid)
    if row is not None:
        if ts > 0 and (row.timestamp <= 0 or ts < row.timestamp):
            row.timestamp = ts
        return row
    row = PulseFrame(pulse_id=pid, timestamp=float(ts or 0.0))
    frames[pid] = row
    return row


def _to_int(v: object, default: int = 0) -> int:
    try:
        return int(v or default)
    except Exception:
        return int(default)


def _is_trigger_intent_key(intent_key: str) -> bool:
    ik = str(intent_key or "").strip()
    return ik.startswith("event.") or ik.startswith("inbox.") or ik.startswith("outbox.")


def _intent_origin(ik: str, source_kind: str, payload: dict[str, object], pulse_id: str) -> str:
    explicit = str(payload.get("origin", "") or "").strip().lower()
    if explicit in {"angelia", "external", "internal"}:
        return explicit
    if ik.startswith("event."):
        return "angelia"
    if ik.startswith("inbox.") or ik.startswith("outbox."):
        if ik.startswith("inbox.section.") or ik in {"inbox.summary", "inbox.read_ack"}:
            return "external"
        # Mail intents with pulse_id typically come from Angelia queue handling.
        if pulse_id or source_kind == "event":
            return "angelia"
        return "external"
    if source_kind in {"event", "trigger"}:
        return "angelia"
    if source_kind in {"llm", "tool", "agent", "phase"}:
        return "internal"
    return "external"


def _intent_lane(ik: str) -> str:
    if ik == "phase.pulse.start":
        return "trigger"
    if _is_trigger_intent_key(ik):
        return "trigger"
    if ik == "llm.response":
        return "agentresponse"
    if ik.startswith("tool.call.") or ik.startswith("tool."):
        return "tool"
    return "other"


def _atom_from_card(card: dict, legacy_idx: int) -> tuple[XmlIntentAtom, int]:
    meta = dict((card or {}).get("meta", {}) or {})
    payload = dict(meta.get("payload", {}) or {}) if isinstance(meta.get("payload"), dict) else {}
    ik = str(meta.get("intent_key", "") or "").strip()
    source_kind = str(meta.get("source_kind", "") or "")
    ts = float((card or {}).get("created_at", 0.0) or 0.0)
    pulse_id = str(meta.get("pulse_id", "") or payload.get("pulse_id", "") or "").strip()
    if not pulse_id:
        legacy_idx += 1
        pulse_id = f"pulse_legacy_{legacy_idx:04d}"
    lane = _intent_lane(ik)
    atom = XmlIntentAtom(
        pulse_id=pulse_id,
        intent_key=ik,
        source_kind=source_kind,
        origin=_intent_origin(ik, source_kind, payload, pulse_id),
        lane=lane,  # type: ignore[arg-type]
        timestamp=ts,
        anchor_seq=_to_int(meta.get("anchor_seq", payload.get("anchor_seq", 0)), 0),
        item_type=str(payload.get("event_type", "") or payload.get("msg_type", "") or ik),
        item_id=str(payload.get("event_id", "") or payload.get("message_id", "") or payload.get("event_ids", "") or ""),
        title=str(payload.get("title", "") or payload.get("section", "") or ""),
        sender=str(payload.get("sender", "") or payload.get("to_agent_id", "") or ""),
        content=_clean_context_payload_text(payload.get("content", "") or (card or {}).get("text", "")),
        args=_sanitize_tool_args(dict(payload.get("args", {}) or {})) if isinstance(payload.get("args"), dict) else {},
        result=_clean_context_payload_text(payload.get("result", "") or (card or {}).get("text", "")),
        call_id=str(payload.get("call_id", "") or ""),
        status=str(payload.get("status", "") or ""),
        attrs=payload,
    )
    return atom, legacy_idx


def _trigger_priority(item: PulseTriggerItem) -> int:
    # Angelia-origin triggers first, external triggers second.
    origin = str(item.origin or "")
    return 0 if origin == "angelia" else 1


def _dedupe_triggers(items: list[PulseTriggerItem]) -> list[PulseTriggerItem]:
    out: list[PulseTriggerItem] = []
    seen: set[str] = set()
    for it in sorted(items, key=_trigger_priority):
        key = f"{it.kind}|{it.item_type}|{it.item_id}|{it.title}|{it.sender}|{str(it.content or '').strip()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _append_tool_call_xml(parent: ET.Element, tc: PulseToolCallItem) -> None:
    tc_el = ET.SubElement(
        parent,
        "tool_call",
        {
            "name": _xml_safe_text(tc.name),
            "status": _xml_safe_text(tc.status),
        },
    )
    args_el = ET.SubElement(tc_el, "args")
    args_el.text = _xml_safe_text(_json_text(_sanitize_tool_args(dict(tc.args or {}))))
    result_el = ET.SubElement(tc_el, "result")
    result_el.text = _xml_safe_text(_clean_context_payload_text(tc.result))


def build_pulse_frames(cards: list[dict]) -> list[PulseFrame]:
    frames: OrderedDict[str, PulseFrame] = OrderedDict()
    legacy_idx = 0
    pending_legacy_triggers: list[PulseTriggerItem] = []
    legacy_call_pulse: dict[str, str] = {}

    for card in list(cards or []):
        atom, legacy_idx = _atom_from_card(card, legacy_idx)
        # Legacy normalization: bind tool.call + tool.result with same call_id into one pulse.
        if atom.pulse_id.startswith("pulse_legacy_") and atom.lane == "tool":
            cid = str(atom.call_id or "").strip()
            if cid:
                if atom.intent_key.startswith("tool.call."):
                    legacy_call_pulse[cid] = atom.pulse_id
                else:
                    bound = legacy_call_pulse.get(cid, "")
                    if bound:
                        atom.pulse_id = bound

        if atom.pulse_id.startswith("pulse_legacy_") and atom.lane == "trigger":
            # Legacy intents may miss pulse_id; keep trigger payload and attach to next response pulse.
            if atom.intent_key.startswith("event."):
                stage = str(atom.attrs.get("stage", "") or "").strip().lower()
                if not stage or stage in {"trigger", "processing"}:
                    tr = PulseTriggerItem(
                        kind="event",
                        origin=atom.origin,  # type: ignore[arg-type]
                        item_type=str(atom.attrs.get("event_type", "") or atom.intent_key.removeprefix("event.")),
                        item_id=str(atom.attrs.get("event_id", "") or atom.item_id),
                        content=atom.content,
                    )
                    pending_legacy_triggers.append(tr)
            elif atom.intent_key.startswith("inbox.") or atom.intent_key.startswith("outbox."):
                tr = PulseTriggerItem(
                    kind="email",
                    origin=atom.origin,  # type: ignore[arg-type]
                    item_type=str(atom.attrs.get("msg_type", "") or atom.intent_key),
                    item_id=str(atom.attrs.get("message_id", "") or atom.attrs.get("event_ids", "") or atom.item_id),
                    title=str(atom.attrs.get("title", "") or atom.attrs.get("section", "") or atom.intent_key),
                    sender=str(atom.attrs.get("sender", "") or atom.attrs.get("to_agent_id", "") or atom.sender),
                    content=atom.content,
                )
                pending_legacy_triggers.append(tr)
            continue

        frame = _frame_for(frames, atom.pulse_id, atom.timestamp)
        if pending_legacy_triggers and not frame.triggers:
            frame.triggers.extend(pending_legacy_triggers)
            pending_legacy_triggers = []

        ik = atom.intent_key
        payload = atom.attrs

        if ik.startswith("event."):
            stage = str(payload.get("stage", "") or "").strip().lower()
            if stage and stage not in {"trigger", "processing"}:
                continue
            tr = PulseTriggerItem(
                kind="event",
                origin=atom.origin,  # type: ignore[arg-type]
                item_type=str(payload.get("event_type", "") or ik.removeprefix("event.")),
                item_id=str(payload.get("event_id", "") or ""),
                content=atom.content,
            )
            frame.triggers.append(tr)
            continue

        if ik == "phase.pulse.start":
            # Lifecycle marker only; never treated as trigger cause.
            continue

        if ik.startswith("inbox.") or ik.startswith("outbox."):
            tr = PulseTriggerItem(
                kind="email",
                origin=atom.origin,  # type: ignore[arg-type]
                item_type=str(payload.get("msg_type", "") or ik),
                item_id=str(payload.get("message_id", "") or payload.get("event_ids", "")),
                title=str(payload.get("title", "") or payload.get("section", "") or ik),
                sender=str(payload.get("sender", "") or payload.get("to_agent_id", "") or ""),
                content=atom.content,
            )
            frame.triggers.append(tr)
            continue

        if ik == "llm.response":
            txt = str(payload.get("content", "") or atom.content).strip()
            if txt:
                if frame.agent_response.text:
                    frame.agent_response.text += "\n" + txt
                else:
                    frame.agent_response.text = txt
                frame.agent_response.segments.append(
                    PulseAgentResponseSegment(kind="text", seq=max(0, int(atom.anchor_seq or 0)), text=txt)
                )
            continue

        if ik.startswith("tool.call."):
            call_id = str(payload.get("call_id", "") or "")
            name = str(payload.get("tool_name", "") or ik.removeprefix("tool.call."))
            tool = PulseToolCallItem(
                name=name,
                call_id=call_id,
                status="",
                args=_sanitize_tool_args(dict(payload.get("args", {}) or {})),
                result="",
            )
            frame.agent_response.tool_calls.append(tool)
            frame.agent_response.segments.append(
                PulseAgentResponseSegment(kind="tool", seq=max(0, int(atom.anchor_seq or 0)), tool_call=tool)
            )
            continue

        if ik.startswith("tool."):
            call_id = str(payload.get("call_id", "") or "")
            name = str(payload.get("tool_name", "") or "")
            status = str(payload.get("status", "") or "")
            result = str(payload.get("result", "") or atom.content)
            target = None
            for tc in frame.agent_response.tool_calls:
                if call_id and tc.call_id == call_id:
                    target = tc
                    break
            if target is None:
                target = PulseToolCallItem(
                    name=name or ik,
                    call_id=call_id,
                    args=_sanitize_tool_args(dict(payload.get("args", {}) or {})),
                )
                frame.agent_response.tool_calls.append(target)
            target.status = status or target.status
            target.result = _clean_context_payload_text(result or target.result)
            frame.agent_response.segments.append(
                PulseAgentResponseSegment(
                    kind="tool",
                    seq=max(0, int(atom.anchor_seq or 0)),
                    tool_call=PulseToolCallItem(
                        name=target.name,
                        call_id=target.call_id,
                        status=target.status,
                        args=dict(target.args or {}),
                        result=target.result,
                    ),
                )
            )
            continue

        # Fallback: keep semantic text for non-tool/non-trigger cards (e.g. summary cards).
        txt = str(atom.content or "").strip()
        if txt:
            if frame.agent_response.text:
                frame.agent_response.text += "\n" + txt
            else:
                frame.agent_response.text = txt
            frame.agent_response.segments.append(
                PulseAgentResponseSegment(kind="text", seq=max(0, int(atom.anchor_seq or 0)), text=txt)
            )

    # Flush legacy-only trigger tail so they are never silently dropped.
    if pending_legacy_triggers:
        legacy_idx += 1
        tail_pid = f"pulse_legacy_{legacy_idx:04d}"
        tail = _frame_for(frames, tail_pid, 0.0)
        tail.triggers.extend(pending_legacy_triggers)
        pending_legacy_triggers = []

    for frame in frames.values():
        frame.triggers = _dedupe_triggers(frame.triggers)

    return list(frames.values())


def render_tagged_context(
    *,
    profile_text: str,
    directives_text: str,
    task_state_text: str,
    tools_text: str,
    inbox_hint_text: str,
    pulse_frames: list[PulseFrame],
) -> str:
    root = ET.Element("context")

    def _append_text(tag: str, text: str) -> None:
        el = ET.SubElement(root, tag)
        el.text = _xml_safe_text(text)

    # Head static blocks
    _append_text("profile", profile_text)
    _append_text("directives", directives_text)
    _append_text("task_state", task_state_text)
    _append_text("tools", tools_text)
    _append_text("inbox_hint", inbox_hint_text)

    # Pulses
    for frame in list(pulse_frames or []):
        if not list(frame.triggers or []):
            raise ValueError(f"PULSE_EMPTY_TRIGGER: pulse_id={str(frame.pulse_id or '')}")
        pulse_el = ET.SubElement(
            root,
            "pulse",
            {
                "id": _xml_safe_text(frame.pulse_id),
                "state": _xml_safe_text(getattr(frame, "state", "processing")),
            },
        )
        trigger_el = ET.SubElement(pulse_el, "trigger")
        for tr in frame.triggers:
            if tr.kind == "email":
                node = ET.SubElement(
                    trigger_el,
                    "email",
                    {
                        "origin": _xml_safe_text(tr.origin),
                        "type": _xml_safe_text(tr.item_type),
                        "id": _xml_safe_text(tr.item_id),
                        "title": _xml_safe_text(tr.title),
                        "sender": _xml_safe_text(tr.sender),
                    },
                )
                node.text = _xml_safe_text(tr.content)
            else:
                node = ET.SubElement(
                    trigger_el,
                    "event",
                    {
                        "origin": _xml_safe_text(tr.origin),
                        "type": _xml_safe_text(tr.item_type),
                        "id": _xml_safe_text(tr.item_id),
                    },
                )
                node.text = _xml_safe_text(tr.content)

        ar: PulseAgentResponse = frame.agent_response
        ar_el = ET.SubElement(pulse_el, "agentresponse")
        segments = list(getattr(ar, "segments", []) or [])
        if segments:
            ordered = sorted(
                segments,
                key=lambda s: (int(getattr(s, "seq", 0) or 0), 0 if getattr(s, "kind", "") == "text" else 1),
            )
            for seg in ordered:
                if str(getattr(seg, "kind", "") or "") == "tool":
                    tc = getattr(seg, "tool_call", None)
                    if tc is not None:
                        _append_tool_call_xml(ar_el, tc)
                else:
                    text_el = ET.SubElement(ar_el, "textresponse")
                    text_el.text = _xml_safe_text(str(getattr(seg, "text", "") or ""))
        else:
            text_el = ET.SubElement(ar_el, "textresponse")
            text_el.text = _xml_safe_text(ar.text)
            for tc in ar.tool_calls:
                _append_tool_call_xml(ar_el, tc)

    # Tail summaries
    _append_text("profile_summary", _summary(profile_text))
    _append_text("task_state_summary", _summary(task_state_text))
    _append_text("inbox_hint_summary", _summary(inbox_hint_text))

    ET.indent(root, space="  ")
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8").rstrip() + "\n"


def extract_static_materials(cards: list[dict], *, directives: str, tools_desc: str, inbox_hint: str) -> dict[str, str]:
    by_key: dict[str, str] = {}
    for card in list(cards or []):
        meta = dict((card or {}).get("meta", {}) or {})
        ik = str(meta.get("intent_key", "") or "").strip()
        if not ik.startswith("material."):
            continue
        by_key[ik] = str((card or {}).get("text", "") or "")

    profile_text = _clean_material_text(by_key.get("material.profile", ""), "PROFILE")
    task_state_text = _clean_material_text(by_key.get("material.task_state", ""), "TASK_STATE")
    tools_text = str(tools_desc or "").strip()
    if not tools_text:
        tools_text = _clean_material_text(by_key.get("material.tools", ""), "TOOLS")
    directives_text = str(directives or "").strip()
    if not directives_text:
        directives_text = _clean_material_text(by_key.get("material.directives", ""), "DIRECTIVES")
    inbox_hint_text = str(inbox_hint or "").strip()

    return {
        "profile": profile_text,
        "task_state": task_state_text,
        "tools": tools_text,
        "directives": directives_text,
        "inbox_hint": inbox_hint_text,
    }
