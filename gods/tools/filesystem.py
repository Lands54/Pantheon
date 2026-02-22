"""
Gods Tools - Filesystem Module
File reading, writing, and manipulation tools with territory isolation.
"""
from pathlib import Path
import builtins
import json
import os
from langchain_core.tools import tool

from gods.hestia import facade as hestia_facade
from gods.identity import is_valid_agent_id
from gods.iris.facade import list_outbox_receipts
from gods.iris.store import list_mail_events
from gods.hermes import facade as hermes_facade
from gods.mnemosyne import facade as mnemosyne_facade
from gods.runtime import facade as runtime_facade
from gods.paths import agent_dir, mnemosyne_dir, project_dir

RESERVED_SYSTEM_FILES = {"memory.md", "memory_archive.md", "agent.md", "runtime_state.json"}
HIDDEN_DIR_NAMES = {"debug"}
MAIL_SCHEME = "mail://"
ARTIFACT_SCHEME = "artifact://"
CONTRACT_SCHEME = "contract://"
AGENT_SCHEME = "agent://"
DETACH_SCHEME = "detach://"


def _is_reserved_path(path: Path, agent_territory: Path) -> bool:
    """
    Checks if a given path corresponds to a reserved system file.
    """
    try:
        rel = path.resolve().relative_to(agent_territory.resolve())
    except Exception:
        return False
    return any(part in RESERVED_SYSTEM_FILES for part in rel.parts)


def validate_path(caller_id: str, project_id: str, path: str) -> Path:
    """
    Validates that a requested path is within the agent's project territory.
    """
    agent_territory = _agent_territory(project_id, caller_id)
    
    # Ensure directory exists for new agents
    agent_territory.mkdir(parents=True, exist_ok=True)
    
    target_path = (agent_territory / path).resolve()

    try:
        target_path.relative_to(agent_territory)
    except ValueError:
        raise PermissionError(f"Divine Restriction: Access to {path} is forbidden. You are confined to your domain.")

    return target_path


def _agent_territory(project_id: str, caller_id: str) -> Path:
    territory = agent_dir(project_id, caller_id).resolve()
    territory.mkdir(parents=True, exist_ok=True)
    return territory


def _cwd_prefix(agent_territory: Path, message: str) -> str:
    """
    Prefixes a message with the agent's current working directory context.
    """
    return f"[Current CWD: {agent_territory}] Content: {message}"


def _format_fs_error(agent_territory: Path, title: str, reason: str, suggestion: str) -> str:
    """
    Formats a filesystem error message with context and suggestions.
    """
    return _cwd_prefix(
        agent_territory,
        f"{title}: {reason}\nSuggested next step: {suggestion}",
    )


def _normalize_to_territory(path: str, caller_id: str) -> str:
    """
    Removes redundant path prefixes to normalize paths relative to the agent's territory.
    """
    marker = f"/agents/{caller_id}/"
    p = path.replace("\\", "/")
    if marker in p:
        return p.split(marker, 1)[1]
    return path


def _find_name_suggestions(agent_territory: Path, path: str, limit: int = 3) -> list[str]:
    """
    Searches for files with similar names to provide suggestions for missing paths.
    """
    basename = Path(path).name
    if not basename:
        return []
    out = []
    try:
        for cand in agent_territory.rglob(basename):
            rel = cand.relative_to(agent_territory)
            if any(part in RESERVED_SYSTEM_FILES for part in rel.parts):
                continue
            out.append(str(rel))
            if len(out) >= limit:
                break
    except Exception:
        return []
    return out


def _missing_read_hint(path: str, caller_id: str, agent_territory: Path) -> str:
    """
    Generates hints for missing files during a read operation.
    """
    hints = []
    normalized = _normalize_to_territory(path, caller_id)
    if normalized != path:
        hints.append(f"detected extra prefix; try '{normalized}'")

    suggestions = _find_name_suggestions(agent_territory, normalized)
    if suggestions:
        hints.append("found similarly named files: " + ", ".join([f"'{s}'" for s in suggestions]))

    if hints:
        return f" Hint: {'; '.join(hints)}."
    return ""


def _path_lookup_hint(path: str, caller_id: str, agent_territory: Path) -> str:
    """
    Provides suggestions for resolving path errors.
    """
    normalized = _normalize_to_territory(path, caller_id)
    suggestions = _find_name_suggestions(agent_territory, normalized)
    if suggestions:
        return f"Try one of: {', '.join(suggestions)}."
    if normalized != path:
        return f"Try path '{normalized}' (removed redundant prefix)."
    return "Check the path with list('.') first, then retry with a relative path."


def _parse_positive_int(value: int, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(int(value), high))
    except Exception:
        return default


def _slice_page(rows: list, page: int, page_size: int) -> list:
    p = _parse_positive_int(page, 1, 1, 100000)
    sz = _parse_positive_int(page_size, 20, 1, 200)
    start = (p - 1) * sz
    end = start + sz
    return builtins.list(rows)[start:end]


def _read_artifact_virtual(agent_territory: Path, artifact_id: str, caller_id: str, project_id: str, start: int, end: int) -> str:
    ref = mnemosyne_facade.head_artifact(artifact_id, caller_id, project_id)
    data = mnemosyne_facade.get_artifact_bytes(artifact_id, caller_id, project_id)
    s = int(start or 1)
    e = int(end or 0)
    if s < 1:
        return _format_fs_error(
            agent_territory,
            "Range Error",
            "start must be >= 1.",
            "Pass start as a 1-based line number (e.g., start=1).",
        )
    if e > 0 and e < s:
        return _format_fs_error(
            agent_territory,
            "Range Error",
            "end must be >= start (or 0 for EOF).",
            "Use start/end with 1-based inclusive numbers, or set end=0 to read to EOF.",
        )
    try:
        text = data.decode("utf-8")
    except Exception:
        body = (
            "[READ_ARTIFACT]\n"
            f"path: {ARTIFACT_SCHEME}{ref.artifact_id}\n"
            f"artifact_id: {ref.artifact_id}\n"
            f"scope: {ref.scope}\n"
            f"mime: {ref.mime}\n"
            f"size: {ref.size}\n"
            f"sha256: {ref.sha256}\n"
            "content: <binary; text preview unavailable>"
        )
        return _cwd_prefix(agent_territory, body)

    lines = text.splitlines()
    total = len(lines)
    if total == 0:
        selected = ""
        range_label = f"{s}-0"
    else:
        if s > total:
            return _format_fs_error(
                agent_territory,
                "Range Error",
                f"start={s} exceeds total lines={total}.",
                "Use list() to inspect resources and choose a valid range.",
            )
        end_idx = total if e <= 0 else min(e, total)
        selected = "\n".join(lines[s - 1 : end_idx])
        range_label = f"{s}-{end_idx}"

    body = (
        "[READ_ARTIFACT]\n"
        f"path: {ARTIFACT_SCHEME}{ref.artifact_id}\n"
        f"artifact_id: {ref.artifact_id}\n"
        f"scope: {ref.scope}\n"
        f"mime: {ref.mime}\n"
        f"size: {ref.size}\n"
        f"line_range: {range_label}\n"
        f"total_lines: {total}\n"
        "---\n"
        f"{selected}"
    )
    return _cwd_prefix(agent_territory, body)


def _read_mail_virtual(agent_territory: Path, path_val: str, caller_id: str, project_id: str, start: int, end: int) -> str:
    rel = path_val[len(MAIL_SCHEME):].strip("/")
    parts = [x for x in rel.split("/") if x]
    if len(parts) != 2 or parts[0] not in {"inbox", "outbox"}:
        return _format_fs_error(
            agent_territory,
            "Path Error",
            f"unsupported mail path: {path_val}",
            "Use mail://inbox/<event_id> or mail://outbox/<receipt_id>.",
        )
    box, item_id = parts[0], parts[1]
    s = int(start or 1)
    e = int(end or 0)
    if s < 1:
        return _format_fs_error(agent_territory, "Range Error", "start must be >= 1.", "Pass start=1 or greater.")
    if e > 0 and e < s:
        return _format_fs_error(agent_territory, "Range Error", "end must be >= start (or 0 for EOF).", "Adjust start/end.")

    if box == "inbox":
        rows = list_mail_events(project_id=project_id, agent_id=caller_id, event_type="mail_event", limit=2000)
        target = next((x for x in rows if str(x.event_id) == item_id), None)
        if target is None:
            return _format_fs_error(agent_territory, "Not Found", f"inbox event not found: {item_id}", "List mail://inbox first.")
        text = str(target.content or "")
        lines = text.splitlines()
        total = len(lines)
        if total == 0:
            selected = ""
            range_label = f"{s}-0"
        else:
            if s > total:
                return _format_fs_error(agent_territory, "Range Error", f"start={s} exceeds total lines={total}.", "Use valid line range.")
            end_idx = total if e <= 0 else min(e, total)
            selected = "\n".join(lines[s - 1:end_idx])
            range_label = f"{s}-{end_idx}"
        body = (
            "[READ_MAIL_INBOX]\n"
            f"path: {path_val}\n"
            f"event_id: {target.event_id}\n"
            f"title: {target.title}\n"
            f"sender: {target.sender}\n"
            f"state: {target.state.value}\n"
            f"created_at: {target.created_at}\n"
            f"attachments: {len(builtins.list(target.attachments or []))}\n"
            f"attachment_ids: {','.join(builtins.list(target.attachments or [])[:20])}\n"
            f"line_range: {range_label}\n"
            f"total_lines: {total}\n"
            "---\n"
            f"{selected}"
        )
        return _cwd_prefix(agent_territory, body)

    rows = list_outbox_receipts(project_id=project_id, from_agent_id=caller_id, limit=2000)
    target = next((x for x in rows if str(x.receipt_id) == item_id), None)
    if target is None:
        return _format_fs_error(agent_territory, "Not Found", f"outbox receipt not found: {item_id}", "List mail://outbox first.")
    text = (
        f"title={target.title}\n"
        f"to={target.to_agent_id}\n"
        f"status={target.status.value}\n"
        f"message_id={target.message_id}\n"
        f"error={target.error_message}\n"
        f"created_at={target.created_at}\n"
        f"updated_at={target.updated_at}"
    )
    lines = text.splitlines()
    total = len(lines)
    if total == 0:
        selected = ""
        range_label = f"{s}-0"
    else:
        if s > total:
            return _format_fs_error(agent_territory, "Range Error", f"start={s} exceeds total lines={total}.", "Use valid line range.")
        end_idx = total if e <= 0 else min(e, total)
        selected = "\n".join(lines[s - 1:end_idx])
        range_label = f"{s}-{end_idx}"
    body = (
        "[READ_MAIL_OUTBOX]\n"
        f"path: {path_val}\n"
        f"receipt_id: {target.receipt_id}\n"
        f"line_range: {range_label}\n"
        f"total_lines: {total}\n"
        "---\n"
        f"{selected}"
    )
    return _cwd_prefix(agent_territory, body)


def _list_agents_virtual(path_val: str, caller_id: str, project_id: str, page_size: int, page: int) -> str:
    mode = path_val[len(AGENT_SCHEME):].strip().strip("/") or "reachable"
    if mode not in {"reachable", "all"}:
        return _format_fs_error(
            _agent_territory(project_id, caller_id),
            "Path Error",
            f"unsupported agent path: {path_val}",
            "Use agent://reachable or agent://all.",
        )

    agents_root = project_dir(project_id) / "agents"
    if not agents_root.exists():
        lines = [f"[AGENTS:{mode}] page={page} page_size={page_size} total=0", "[EMPTY] No rows in this page."]
        return _cwd_prefix(_agent_territory(project_id, caller_id), "\n".join(lines))

    visible = set(hestia_facade.list_reachable_agents(project_id=project_id, caller_id=caller_id))
    restrict_by_graph = bool(is_valid_agent_id(caller_id)) and mode == "reachable"
    rows: list[str] = []
    for d in sorted([p for p in agents_root.iterdir() if p.is_dir()]):
        agent_id = str(d.name or "").strip()
        if not is_valid_agent_id(agent_id):
            continue
        if restrict_by_graph and agent_id not in visible:
            continue
        md_path = mnemosyne_dir(project_id) / "agent_profiles" / f"{agent_id}.md"
        role = "No role summary."
        if md_path.exists():
            text = md_path.read_text(encoding="utf-8").strip()
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if lines:
                role = lines[0].replace("#", "").strip()
                for i, ln in enumerate(lines):
                    if ("本体职责" in ln) or ("自身职责" in ln):
                        for j in range(i + 1, len(lines)):
                            cand = lines[j]
                            if cand.startswith("#"):
                                break
                            role = cand[:120]
                            break
                        break
                else:
                    for ln in lines[1:]:
                        if not ln.startswith("#"):
                            role = ln[:120]
                            break
        rows.append(f"[AGENT] id={agent_id} role={role}")

    paged = _slice_page(rows, page=page, page_size=page_size)
    out = [f"[AGENTS:{mode}] page={page} page_size={page_size} total={len(rows)}"]
    out.extend(paged if paged else ["[EMPTY] No rows in this page."])
    return _cwd_prefix(_agent_territory(project_id, caller_id), "\n".join(out))


def _read_contract_virtual(agent_territory: Path, path_val: str, project_id: str, start: int, end: int) -> str:
    ref = path_val[len(CONTRACT_SCHEME):].strip().strip("/")
    if "@" not in ref:
        return _format_fs_error(
            agent_territory,
            "Path Error",
            f"unsupported contract path: {path_val}",
            "Use contract://<title>@<version>, e.g. contract://Library Contract@1.0.0.",
        )
    title, version = ref.rsplit("@", 1)
    title = str(title or "").strip()
    version = str(version or "").strip()
    if not title or not version:
        return _format_fs_error(
            agent_territory,
            "Path Error",
            f"unsupported contract path: {path_val}",
            "Use contract://<title>@<version> with both title and version.",
        )
    s = int(start or 1)
    e = int(end or 0)
    if s < 1:
        return _format_fs_error(agent_territory, "Range Error", "start must be >= 1.", "Pass start=1 or greater.")
    if e > 0 and e < s:
        return _format_fs_error(agent_territory, "Range Error", "end must be >= start (or 0 for EOF).", "Adjust start/end.")
    rows = hermes_facade.list_contracts(project_id, include_disabled=True)
    target = next(
        (
            x
            for x in rows
            if isinstance(x, dict)
            and str(x.get("title", "") or "").strip() == title
            and str(x.get("version", "") or "").strip() == version
        ),
        None,
    )
    if not isinstance(target, dict):
        return _format_fs_error(
            agent_territory,
            "Not Found",
            f"contract not found: {title}@{version}",
            "Use list('contract://active') or list('contract://all') first.",
        )
    serialized = json.dumps(target, ensure_ascii=False, indent=2, sort_keys=True)
    lines = serialized.splitlines()
    total = len(lines)
    if total == 0:
        selected = ""
        range_label = f"{s}-0"
    else:
        if s > total:
            return _format_fs_error(agent_territory, "Range Error", f"start={s} exceeds total lines={total}.", "Use valid line range.")
        end_idx = total if e <= 0 else min(e, total)
        selected = "\n".join(lines[s - 1:end_idx])
        range_label = f"{s}-{end_idx}"
    body = (
        "[READ_CONTRACT]\n"
        f"path: {path_val}\n"
        f"title: {title}\n"
        f"version: {version}\n"
        f"status: {str(target.get('status', '') or '')}\n"
        f"line_range: {range_label}\n"
        f"total_lines: {total}\n"
        "---\n"
        f"{selected}"
    )
    return _cwd_prefix(agent_territory, body)


def _list_detach_virtual(agent_territory: Path, path_val: str, caller_id: str, project_id: str, page_size: int, page: int) -> str:
    rel = path_val[len(DETACH_SCHEME):].strip().strip("/")
    if not rel:
        rel = "jobs"
    parts = [x for x in rel.split("/") if x]
    if not parts or parts[0] != "jobs":
        return _format_fs_error(
            agent_territory,
            "Path Error",
            f"unsupported detach path: {path_val}",
            "Use detach://jobs or detach://jobs/<status>.",
        )
    status = ""
    if len(parts) >= 2:
        status = str(parts[1] or "").strip().lower()
        if status not in {"queued", "running", "stopping", "stopped", "failed", "lost"}:
            return _format_fs_error(
                agent_territory,
                "Path Error",
                f"unsupported detach status filter: {status}",
                "Use one of queued|running|stopping|stopped|failed|lost.",
            )
    rows = runtime_facade.detach_list_for_api(
        project_id=project_id,
        agent_id=caller_id,
        status=status,
        limit=2000,
    ).get("items", [])
    rows = sorted(rows, key=lambda x: float(x.get("created_at", 0) or 0), reverse=True)
    paged = _slice_page(rows, page=page, page_size=page_size)
    lines = [f"[DETACH:jobs] page={page} page_size={page_size} total={len(rows)} status={status or 'all'}"]
    for x in paged:
        lines.append(
            f"[DETACH_JOB] id={x.get('job_id','')} status={x.get('status','')} "
            f"created_at={x.get('created_at','')} command={x.get('command','')}"
        )
    if not paged:
        lines.append("[EMPTY] No rows in this page.")
    return _cwd_prefix(agent_territory, "\n".join(lines))


def _read_detach_virtual(agent_territory: Path, path_val: str, caller_id: str, project_id: str, start: int, end: int) -> str:
    rel = path_val[len(DETACH_SCHEME):].strip().strip("/")
    parts = [x for x in rel.split("/") if x]
    if not parts:
        return _format_fs_error(
            agent_territory,
            "Path Error",
            f"unsupported detach path: {path_val}",
            "Use detach://<job_id> or detach://log/<job_id>.",
        )
    if parts[0] == "jobs":
        return _format_fs_error(
            agent_territory,
            "Path Error",
            f"unsupported detach read path: {path_val}",
            "Use list('detach://jobs') to browse jobs first, then read detach://<job_id>.",
        )
    if parts[0] == "log" and len(parts) == 2:
        job_id = parts[1]
    elif len(parts) == 1:
        job_id = parts[0]
    else:
        return _format_fs_error(
            agent_territory,
            "Path Error",
            f"unsupported detach path: {path_val}",
            "Use detach://<job_id> or detach://log/<job_id>.",
        )

    rows = runtime_facade.detach_list_for_api(
        project_id=project_id,
        agent_id=caller_id,
        status="",
        limit=2000,
    ).get("items", [])
    target = next((x for x in rows if str(x.get("job_id", "")) == str(job_id)), None)
    if not isinstance(target, dict):
        return _format_fs_error(
            agent_territory,
            "Permission Error",
            f"detach job not found (or not owned by caller): {job_id}",
            "Use list('detach://jobs') and read your own job id.",
        )
    payload = runtime_facade.detach_get_logs(project_id=project_id, job_id=job_id) or {}
    text = str(payload.get("tail", "") or "")
    lines = text.splitlines()
    s = int(start or 1)
    e = int(end or 0)
    if s < 1:
        return _format_fs_error(agent_territory, "Range Error", "start must be >= 1.", "Pass start=1 or greater.")
    if e > 0 and e < s:
        return _format_fs_error(agent_territory, "Range Error", "end must be >= start (or 0 for EOF).", "Adjust start/end.")
    total = len(lines)
    if total == 0:
        selected = ""
        range_label = f"{s}-0"
    else:
        if s > total:
            return _format_fs_error(
                agent_territory,
                "Range Error",
                f"start={s} exceeds total lines={total}.",
                "Use valid line range.",
            )
        end_idx = total if e <= 0 else min(e, total)
        selected = "\n".join(lines[s - 1:end_idx])
        range_label = f"{s}-{end_idx}"
    body = (
        "[READ_DETACH_LOG]\n"
        f"path: {path_val}\n"
        f"job_id: {job_id}\n"
        f"status: {str(target.get('status', '') or '')}\n"
        f"line_range: {range_label}\n"
        f"total_lines: {total}\n"
        "---\n"
        f"{selected}"
    )
    return _cwd_prefix(agent_territory, body)


@tool
def read(
    path: str = "",
    caller_id: str = "default",
    project_id: str = "default",
    start: int = 1,
    end: int = 0,
) -> str:
    """
    Read the contents of local files, mailbox records, artifacts, Hermes contracts, or detach logs.
    
    Supported path formats:
    - Local file: Specify the relative path within your territory (e.g., 'src/main.py', 'data.json').
    - Mailbox record: Use 'mail://inbox/<event_id>' to read a received message, or 'mail://outbox/<receipt_id>' to check sent message status.
    - Artifact: Use 'artifact://<artifact_id>' to read the contents of an uploaded binary or text artifact.
    - Contract: Use 'contract://<title>@<version>' to read a Hermes contract detail payload.
    - Detach log: Use 'detach://<job_id>' (or 'detach://log/<job_id>') to read your detach job log.
    
    Pagination/Range reading:
    - Use 'start' and 'end' (1-based, inclusive) to read a specific slice of the text.
    - Example: start=10, end=20 reads lines 10 through 20.
    - Set end=0 (or omit) to read from 'start' to the end of the file.
    """
    try:
        agent_territory = _agent_territory(project_id, caller_id)
        path_val = str(path or "").strip()
        if not path_val:
            return _format_fs_error(agent_territory, "Input Error", "path is required.", "Use local path, mail://..., or artifact://<id>.")
        if path_val.startswith(ARTIFACT_SCHEME):
            aid = path_val[len(ARTIFACT_SCHEME):].strip().strip("/")
            if not aid:
                return _format_fs_error(agent_territory, "Path Error", "missing artifact id in path.", "Use artifact://<artifact_id>.")
            return _read_artifact_virtual(agent_territory, aid, caller_id, project_id, start, end)
        if path_val.startswith(CONTRACT_SCHEME):
            return _read_contract_virtual(agent_territory, path_val, project_id, start, end)
        if path_val.startswith(DETACH_SCHEME):
            return _read_detach_virtual(agent_territory, path_val, caller_id, project_id, start, end)
        if path_val.startswith(MAIL_SCHEME):
            return _read_mail_virtual(agent_territory, path_val, caller_id, project_id, start, end)

        file_path = validate_path(caller_id, project_id, path_val)
        if _is_reserved_path(file_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "Access to system memory files is forbidden.",
                "Do not read memory.md/memory_archive.md/agent.md/runtime_state.json directly. Use normal project files only.",
            )
        if not file_path.exists():
            hint = _missing_read_hint(path_val, caller_id, agent_territory)
            return _format_fs_error(
                agent_territory,
                "Path Error",
                f"Scroll '{path_val}' not found.{hint}",
                _path_lookup_hint(path_val, caller_id, agent_territory),
            )

        s = int(start or 1)
        e = int(end or 0)
        if s < 1:
            return _format_fs_error(
                agent_territory,
                "Range Error",
                "start must be >= 1.",
                "Pass start as a 1-based line number (e.g., start=1).",
            )
        if e > 0 and e < s:
            return _format_fs_error(
                agent_territory,
                "Range Error",
                "end must be >= start (or 0 for EOF).",
                "Use start/end with 1-based inclusive numbers, or set end=0 to read to EOF.",
            )

        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        total = len(lines)
        if total == 0:
            selected = ""
            range_label = f"{s}-0"
        else:
            if s > total:
                return _format_fs_error(
                    agent_territory,
                    "Range Error",
                    f"start={s} exceeds total lines={total}.",
                    "Use list/read to inspect file and choose a valid range.",
                )
            end_idx = total if e <= 0 else min(e, total)
            selected_lines = lines[s - 1:end_idx]
            selected = "\n".join(selected_lines)
            range_label = f"{s}-{end_idx}"

        body = (
            "[READ]\n"
            f"path: {path_val}\n"
            f"resolved_path: {file_path}\n"
            f"line_range: {range_label}\n"
            f"total_lines: {total}\n"
            "---\n"
            f"{selected}"
        )
        return _cwd_prefix(agent_territory, body)
    except Exception as e:
        agent_territory = _agent_territory(project_id, caller_id)
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Verify the path stays inside your territory and retry.",
        )


@tool
def write_file(path: str, content: str, caller_id: str, project_id: str = "default") -> str:
    """Inscribe a new scroll or overwrite an existing one in your territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = _agent_territory(project_id, caller_id)
        if _is_reserved_path(file_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "System memory files are managed by the platform.",
                "Write to your own task files, not memory.md/memory_archive.md/agent.md/runtime_state.json.",
            )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return _cwd_prefix(agent_territory, f"Scroll {path} has been inscribed.")
    except Exception as e:
        agent_territory = _agent_territory(project_id, caller_id)
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Check write permissions and ensure the target path is within your territory.",
        )


@tool
def replace_content(path: str, target_content: str, replacement_content: str, caller_id: str, project_id: str = "default") -> str:
    """Refine the scripture within your project territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = _agent_territory(project_id, caller_id)
        if _is_reserved_path(file_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "System memory files are managed by the platform.",
                "Refine only normal project files.",
            )
        if not file_path.exists():
            return _format_fs_error(
                agent_territory,
                "Path Error",
                f"Scroll {path} not found.",
                _path_lookup_hint(path, caller_id, agent_territory),
            )

        content = file_path.read_text(encoding="utf-8")
        if target_content not in content:
            return _format_fs_error(
                agent_territory,
                "Match Error",
                f"Target sequence not found in {path}.",
                "Read the file first and copy an exact unique snippet as target_content.",
            )

        count = content.count(target_content)
        if count > 1:
            return _format_fs_error(
                agent_territory,
                "Match Error",
                f"Non-unique match ({count} found).",
                "Use a longer unique target_content, or switch to insert_content for anchored edits.",
            )

        new_content = content.replace(target_content, replacement_content)
        file_path.write_text(new_content, encoding="utf-8")
        return _cwd_prefix(agent_territory, f"Sacred scripture {path} has been refined.")
    except Exception as e:
        agent_territory = _agent_territory(project_id, caller_id)
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Retry with a valid relative path and exact target content.",
        )


@tool
def insert_content(path: str, anchor: str, content_to_insert: str, position: str = "after", caller_id: str = "default", project_id: str = "default") -> str:
    """Expand the scripture within your project territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = _agent_territory(project_id, caller_id)
        if _is_reserved_path(file_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "System memory files are managed by the platform.",
                "Insert content only into normal project files.",
            )
        if not file_path.exists():
            return _format_fs_error(
                agent_territory,
                "Path Error",
                f"Scroll {path} not found.",
                _path_lookup_hint(path, caller_id, agent_territory),
            )

        original_content = file_path.read_text(encoding="utf-8")
        if anchor not in original_content:
            return _format_fs_error(
                agent_territory,
                "Anchor Error",
                f"Anchor '{anchor}' not found.",
                "Read the file and use an exact existing anchor string.",
            )
        
        if original_content.count(anchor) > 1:
            return _format_fs_error(
                agent_territory,
                "Anchor Error",
                "Ambiguous anchor.",
                "Use a longer unique anchor text or narrow the target area first.",
            )

        if position == "after":
            new_content = original_content.replace(anchor, anchor + content_to_insert)
        else:
            new_content = original_content.replace(anchor, content_to_insert + anchor)

        file_path.write_text(new_content, encoding="utf-8")
        return _cwd_prefix(agent_territory, f"New passage manifested in {path} ({position} the anchor).")
    except Exception as e:
        agent_territory = _agent_territory(project_id, caller_id)
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Retry with a valid path, anchor and position ('before' or 'after').",
        )


@tool
def multi_replace(path: str, replacements_json: str, caller_id: str, project_id: str = "default") -> str:
    """Reshape the doctrine within your project territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = _agent_territory(project_id, caller_id)
        if _is_reserved_path(file_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "System memory files are managed by the platform.",
                "Run multi_replace only on normal project files.",
            )
        replacements = json.loads(replacements_json)
        content = file_path.read_text(encoding="utf-8")
        for rep in replacements:
            target, repl = rep["target"], rep["replacement"]
            if target not in content or content.count(target) > 1:
                return _format_fs_error(
                    agent_territory,
                    "Match Error",
                    f"Refinement failed for '{target}'.",
                    "Ensure each target exists exactly once before running multi_replace.",
                )
            content = content.replace(target, repl)
        file_path.write_text(content, encoding="utf-8")
        return _cwd_prefix(agent_territory, f"Doctrine in {path} reshaped.")
    except Exception as e:
        agent_territory = _agent_territory(project_id, caller_id)
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Validate replacements_json format and target file path, then retry.",
        )


@tool
def list(path: str = ".", caller_id: str = "default", project_id: str = "default", page_size: int = 20, page: int = 1) -> str:
    """
    List directory contents, mailbox history, artifacts, Hermes contracts, or detach jobs within your territory.
    
    Supported path formats:
    - Agent roster: Use 'agent://reachable' (default) to list agents reachable by Hestia graph, or 'agent://all' to list all agents.
    - Local directory: Pass a standard filesystem path (e.g., '.', 'src', 'data/') to list files and subdirectories.
    - Mailbox history: Use 'mail://inbox' to list received messages or 'mail://outbox' to list sent messages.
    - Artifacts: Use 'artifact://agent', 'artifact://project', or 'artifact://global' to list artifacts within a specific scope.
    - Contracts: Use 'contract://active' (default) or 'contract://all' to list Hermes contracts.
    - Detach jobs: Use 'detach://jobs' (or 'detach://jobs/<status>') to list your detach jobs.
    
    Pagination:
    - Use the 'page' (1-based) and 'page_size' (default 20) arguments to paginate through large directories or long histories.
    """
    try:
        page_size = _parse_positive_int(page_size, 20, 1, 200)
        page = _parse_positive_int(page, 1, 1, 100000)
        path_val = str(path or ".").strip()
        if path_val.startswith(AGENT_SCHEME):
            return _list_agents_virtual(path_val, caller_id, project_id, page_size, page)
        if path_val.startswith(MAIL_SCHEME):
            rel = path_val[len(MAIL_SCHEME):].strip("/")
            if rel not in {"inbox", "outbox"}:
                return _format_fs_error(
                    _agent_territory(project_id, caller_id),
                    "Path Error",
                    f"unsupported mail path: {path_val}",
                    "Use mail://inbox or mail://outbox.",
                )
            if rel == "inbox":
                rows = list_mail_events(project_id=project_id, agent_id=caller_id, event_type="mail_event", limit=2000)
                rows.sort(key=lambda x: x.created_at, reverse=True)
                paged = _slice_page(rows, page=page, page_size=page_size)
                lines = [f"[MAILBOX:inbox] page={page} page_size={page_size} total={len(rows)}"]
                for x in paged:
                    lines.append(
                        f"[MAIL] id={x.event_id} state={x.state.value} from={x.sender} title={x.title} at={x.created_at} attachments={len(builtins.list(x.attachments or []))}"
                    )
                if not paged:
                    lines.append("[EMPTY] No rows in this page.")
                return _cwd_prefix(_agent_territory(project_id, caller_id), "\n".join(lines))
            rows = list_outbox_receipts(project_id=project_id, from_agent_id=caller_id, limit=2000)
            paged = _slice_page(rows, page=page, page_size=page_size)
            lines = [f"[MAILBOX:outbox] page={page} page_size={page_size} total={len(rows)}"]
            for x in paged:
                lines.append(
                    f"[RECEIPT] id={x.receipt_id} status={x.status.value} to={x.to_agent_id} title={x.title} message_id={x.message_id} updated={x.updated_at}"
                )
            if not paged:
                lines.append("[EMPTY] No rows in this page.")
            return _cwd_prefix(_agent_territory(project_id, caller_id), "\n".join(lines))
        if path_val.startswith(ARTIFACT_SCHEME):
            scope = path_val[len(ARTIFACT_SCHEME):].strip().strip("/") or "agent"
            if scope not in {"agent", "project", "global"}:
                return _format_fs_error(
                    _agent_territory(project_id, caller_id),
                    "Path Error",
                    f"unsupported artifact path: {path_val}",
                    "Use artifact://agent, artifact://project, or artifact://global.",
                )
            refs = mnemosyne_facade.list_artifacts(
                scope=scope,
                project_id=project_id,
                actor_id=caller_id,
                limit=page * page_size,
            )
            paged = _slice_page(refs, page=page, page_size=page_size)
            lines = [f"[ARTIFACTS:{scope}] page={page} page_size={page_size} total_visible={len(refs)}"]
            for ref in paged:
                lines.append(
                    f"[ATTACHMENT] id={ref.artifact_id} mime={ref.mime} size={ref.size} owner={ref.owner_agent_id or '-'}"
                )
            if not paged:
                lines.append("[EMPTY] No rows in this page.")
            return _cwd_prefix(_agent_territory(project_id, caller_id), "\n".join(lines))
        if path_val.startswith(CONTRACT_SCHEME):
            rel = path_val[len(CONTRACT_SCHEME):].strip().strip("/") or "active"
            if rel not in {"active", "all"}:
                return _format_fs_error(
                    _agent_territory(project_id, caller_id),
                    "Path Error",
                    f"unsupported contract path: {path_val}",
                    "Use contract://active or contract://all.",
                )
            rows = hermes_facade.list_contracts(project_id, include_disabled=(rel == "all"))
            paged = _slice_page(rows, page=page, page_size=page_size)
            lines = [f"[CONTRACTS:{rel}] page={page} page_size={page_size} total={len(rows)}"]
            for row in paged:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    f"[CONTRACT] id={row.get('title','')}@{row.get('version','')} status={row.get('status','')} "
                    f"fully_committed={bool(row.get('is_fully_committed', False))}"
                )
            if not paged:
                lines.append("[EMPTY] No rows in this page.")
            return _cwd_prefix(_agent_territory(project_id, caller_id), "\n".join(lines))
        if path_val.startswith(DETACH_SCHEME):
            return _list_detach_virtual(_agent_territory(project_id, caller_id), path_val, caller_id, project_id, page_size, page)

        dir_path = validate_path(caller_id, project_id, path_val)
        agent_territory = _agent_territory(project_id, caller_id)
        if _is_reserved_path(dir_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "Access to system memory files is forbidden.",
                "List normal directories only.",
            )
        if not dir_path.exists():
            return _format_fs_error(
                agent_territory,
                "Path Error",
                f"Path {path} not found.",
                _path_lookup_hint(path, caller_id, agent_territory),
            )
        if not dir_path.is_dir():
            return _format_fs_error(
                agent_territory,
                "Type Error",
                f"Path {path} is not a directory.",
                "Use read for files/artifacts, or pass a directory path to list.",
            )

        items = sorted([
            item for item in os.listdir(dir_path)
            if (not item.startswith('.'))
            and (item not in RESERVED_SYSTEM_FILES)
            and (item not in HIDDEN_DIR_NAMES)
        ])
        result: list[str] = []
        if items:
            result.append("[LOCAL]")
            result.extend(
                [f"{'[CHAMBER]' if (dir_path / item).is_dir() else '[SCROLL]'} {item}" for item in items]
            )
        else:
            result.append("[LOCAL]\n[EMPTY] No visible files or directories.")

        artifact_lines: list[str] = []
        for scope in ("agent", "project", "global"):
            refs = mnemosyne_facade.list_artifacts(
                scope=scope,
                project_id=project_id,
                actor_id=caller_id,
                limit=min(10, page_size),
            )
            if not refs:
                continue
            artifact_lines.append(f"[ARTIFACTS:{scope}]")
            for ref in refs:
                artifact_lines.append(
                    f"[ATTACHMENT] id={ref.artifact_id} mime={ref.mime} size={ref.size} owner={ref.owner_agent_id or '-'}"
                )
        if artifact_lines:
            result.append("")
            result.extend(artifact_lines)
        return _cwd_prefix(agent_territory, "\n".join(result))
    except Exception as e:
        agent_territory = _agent_territory(project_id, caller_id)
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Retry with a valid relative path within your territory.",
        )
