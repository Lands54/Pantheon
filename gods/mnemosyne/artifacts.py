"""Mnemosyne artifact storage (namespace + immutable blobs)."""
from __future__ import annotations

import fcntl
import hashlib
import json
import mimetypes
import re
import time
from pathlib import Path
from typing import Any

from gods.mnemosyne.artifact_acl import evaluate_artifact_acl
from gods.mnemosyne.artifact_contracts import ArtifactRef, ArtifactScope
from gods.paths import mnemosyne_dir, projects_root

_ARTIFACT_ID_RE = re.compile(r"^artf_[a-f0-9]{12}_[0-9]{13}$")


def is_valid_artifact_id(value: str) -> bool:
    return bool(_ARTIFACT_ID_RE.match(str(value or "").strip()))


def _normalize_scope(scope: str) -> ArtifactScope:
    sc = str(scope or "").strip().lower()
    if sc not in {"global", "project", "agent"}:
        raise ValueError("scope must be global|project|agent")
    return sc  # type: ignore[return-value]


def _project_key(scope: ArtifactScope, project_id: str) -> str:
    if scope == "global":
        return "_global"
    pid = str(project_id or "").strip()
    if not pid:
        raise ValueError("project_id is required for project/agent scope")
    return pid


def _artifacts_root(scope: ArtifactScope, project_key: str) -> Path:
    if scope == "global":
        p = projects_root() / project_key / "mnemosyne" / "artifacts"
    else:
        p = mnemosyne_dir(project_key) / "artifacts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _index_path(scope: ArtifactScope, project_key: str) -> Path:
    return _artifacts_root(scope, project_key) / "index.jsonl"


def _lock_path(scope: ArtifactScope, project_key: str) -> Path:
    p = _artifacts_root(scope, project_key) / "index.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch(exist_ok=True)
    return p


def _blobs_dir(scope: ArtifactScope, project_key: str) -> Path:
    p = _artifacts_root(scope, project_key) / "blobs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _grants_path(scope: ArtifactScope, project_key: str) -> Path:
    return _artifacts_root(scope, project_key) / "grants.json"


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _with_lock(scope: ArtifactScope, project_key: str, mutator):
    lock = _lock_path(scope, project_key)
    idx = _index_path(scope, project_key)
    with lock.open("r+", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            rows = _read_rows(idx)
            rows2, result = mutator(rows)
            _write_rows(idx, rows2)
            return result
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _row_to_ref(row: dict[str, Any]) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=str(row.get("artifact_id", "")),
        scope=str(row.get("scope", "project")),  # type: ignore[arg-type]
        project_id=str(row.get("project_id", "")),
        owner_agent_id=str(row.get("owner_agent_id", "")),
        mime=str(row.get("mime", "application/octet-stream")),
        size=int(row.get("size", 0)),
        sha256=str(row.get("sha256", "")),
        created_at=float(row.get("created_at", 0.0)),
    )


def _blob_path(scope: ArtifactScope, project_key: str, sha256_hex: str) -> Path:
    return _blobs_dir(scope, project_key) / f"{sha256_hex}.bin"


def _guess_ext(mime: str) -> str:
    if mime == "application/json":
        return ".json"
    if mime in {"text/markdown", "text/x-markdown"}:
        return ".md"
    ext = mimetypes.guess_extension(mime or "")
    return ext or ".bin"


def put_artifact_bytes(
    scope: str,
    project_id: str,
    owner_agent_id: str,
    actor_id: str,
    data: bytes,
    mime: str = "application/octet-stream",
    tags: list[str] | None = None,
) -> ArtifactRef:
    sc = _normalize_scope(scope)
    project_key = _project_key(sc, project_id)
    sha = hashlib.sha256(data).hexdigest()
    now = time.time()
    owner = str(owner_agent_id or "").strip()
    mime_val = str(mime or "application/octet-stream").strip() or "application/octet-stream"
    if sc == "agent" and not owner:
        raise ValueError("owner_agent_id is required for agent scope")

    proposal = ArtifactRef(
        artifact_id=f"artf_{sha[:12]}_{int(now * 1000)}",
        scope=sc,
        project_id=("" if sc == "global" else str(project_id or "").strip()),
        owner_agent_id=owner,
        mime=mime_val,
        size=len(data),
        sha256=sha,
        created_at=now,
    )
    acl = evaluate_artifact_acl(proposal, actor_id=actor_id, project_id=project_id, action="write")
    if not acl.allowed:
        raise PermissionError(acl.reason)

    def _mut(rows: list[dict[str, Any]]):
        for row in rows:
            if (
                str(row.get("scope", "")) == sc
                and str(row.get("project_id", "")) == proposal.project_id
                and str(row.get("owner_agent_id", "")) == proposal.owner_agent_id
                and str(row.get("sha256", "")) == sha
            ):
                return rows, _row_to_ref(row)
        row = {
            "artifact_id": proposal.artifact_id,
            "scope": proposal.scope,
            "project_id": proposal.project_id,
            "owner_agent_id": proposal.owner_agent_id,
            "mime": proposal.mime,
            "size": proposal.size,
            "sha256": proposal.sha256,
            "created_at": proposal.created_at,
            "tags": [str(x).strip() for x in list(tags or []) if str(x).strip()],
        }
        rows.append(row)
        return rows, _row_to_ref(row)

    ref = _with_lock(sc, project_key, _mut)
    blob = _blob_path(sc, project_key, ref.sha256)
    if not blob.exists():
        blob.write_bytes(data)
    return ref


def put_artifact_text(
    scope: str,
    project_id: str,
    owner_agent_id: str,
    actor_id: str,
    text: str,
    mime: str = "text/plain",
    tags: list[str] | None = None,
) -> ArtifactRef:
    return put_artifact_bytes(
        scope=scope,
        project_id=project_id,
        owner_agent_id=owner_agent_id,
        actor_id=actor_id,
        data=str(text or "").encode("utf-8"),
        mime=mime,
        tags=tags,
    )


def _find_artifact_row(artifact_id: str, project_id: str) -> tuple[dict[str, Any], ArtifactScope, str]:
    aid = str(artifact_id or "").strip()
    if not is_valid_artifact_id(aid):
        raise ValueError("invalid artifact_id")
    pid = str(project_id or "").strip()
    for scope, key in (("project", pid), ("agent", pid), ("global", "_global")):
        if scope in {"project", "agent"} and not key:
            continue
        rows = _read_rows(_index_path(scope, key))  # type: ignore[arg-type]
        for row in rows:
            if str(row.get("scope", "")).strip().lower() != scope:
                continue
            if str(row.get("artifact_id", "")) == aid:
                return row, scope, key  # type: ignore[return-value]
    raise FileNotFoundError(f"artifact not found: {aid}")


def _read_grants(scope: ArtifactScope, project_key: str) -> dict[str, list[str]]:
    p = _grants_path(scope, project_key)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for k, v in raw.items():
        key = str(k or "").strip()
        if not key:
            continue
        rows = [str(x).strip() for x in list(v or []) if str(x).strip()]
        out[key] = sorted(set(rows))
    return out


def _write_grants(scope: ArtifactScope, project_key: str, grants: dict[str, list[str]]) -> None:
    p = _grants_path(scope, project_key)
    p.parent.mkdir(parents=True, exist_ok=True)
    clean: dict[str, list[str]] = {}
    for k, v in grants.items():
        key = str(k or "").strip()
        if not key:
            continue
        rows = [str(x).strip() for x in list(v or []) if str(x).strip()]
        clean[key] = sorted(set(rows))
    p.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def list_artifact_grants(artifact_id: str, project_id: str) -> list[str]:
    _, scope, key = _find_artifact_row(artifact_id, project_id)
    if scope != "agent":
        return []
    rows = _read_grants(scope, key)
    return [str(x).strip() for x in list(rows.get(str(artifact_id), []) or []) if str(x).strip()]


def grant_artifact_access(
    artifact_id: str,
    project_id: str,
    owner_actor_id: str,
    target_agent_id: str,
) -> list[str]:
    row, scope, key = _find_artifact_row(artifact_id, project_id)
    ref = _row_to_ref(row)
    target = str(target_agent_id or "").strip()
    if not target:
        raise ValueError("target_agent_id is required")
    if scope != "agent":
        raise ValueError("grant is only supported for agent-scope artifacts")
    write_acl = evaluate_artifact_acl(ref, actor_id=owner_actor_id, project_id=project_id, action="write")
    if not write_acl.allowed:
        raise PermissionError(write_acl.reason)
    grants = _read_grants(scope, key)
    existing = [str(x).strip() for x in list(grants.get(ref.artifact_id, []) or []) if str(x).strip()]
    if target not in existing:
        existing.append(target)
    grants[ref.artifact_id] = sorted(set(existing))
    _write_grants(scope, key, grants)
    return grants[ref.artifact_id]


def head_artifact(artifact_id: str, actor_id: str, project_id: str) -> ArtifactRef:
    row, scope, key = _find_artifact_row(artifact_id, project_id)
    ref = _row_to_ref(row)
    grants = set(_read_grants(scope, key).get(ref.artifact_id, [])) if scope == "agent" else set()
    acl = evaluate_artifact_acl(
        ref,
        actor_id=actor_id,
        project_id=project_id,
        action="read",
        granted_agents=grants,
    )
    if not acl.allowed:
        raise PermissionError(acl.reason)
    return ref


def get_artifact_bytes(artifact_id: str, actor_id: str, project_id: str) -> bytes:
    row, scope, key = _find_artifact_row(artifact_id, project_id)
    ref = _row_to_ref(row)
    grants = set(_read_grants(scope, key).get(ref.artifact_id, [])) if scope == "agent" else set()
    acl = evaluate_artifact_acl(
        ref,
        actor_id=actor_id,
        project_id=project_id,
        action="read",
        granted_agents=grants,
    )
    if not acl.allowed:
        raise PermissionError(acl.reason)
    blob = _blob_path(scope, key, ref.sha256)
    if not blob.exists():
        raise FileNotFoundError(f"artifact blob missing: {artifact_id}")
    return blob.read_bytes()


def materialize_artifact(artifact_id: str, actor_id: str, project_id: str, target_dir: str) -> str:
    ref = head_artifact(artifact_id, actor_id, project_id)
    data = get_artifact_bytes(artifact_id, actor_id, project_id)
    d = Path(str(target_dir or "").strip())
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{ref.artifact_id}{_guess_ext(ref.mime)}"
    path.write_bytes(data)
    return str(path)


def list_artifacts(
    scope: str,
    project_id: str,
    actor_id: str,
    owner_agent_id: str = "",
    limit: int = 50,
) -> list[ArtifactRef]:
    sc = _normalize_scope(scope)
    key = _project_key(sc, project_id)
    rows = list(_read_rows(_index_path(sc, key)))
    out: list[ArtifactRef] = []
    owner = str(owner_agent_id or "").strip()
    for row in reversed(rows):
        ref = _row_to_ref(row)
        if str(ref.scope).strip().lower() != sc:
            continue
        if owner and ref.owner_agent_id != owner:
            continue
        grants = set(_read_grants(sc, key).get(ref.artifact_id, [])) if sc == "agent" else set()
        acl = evaluate_artifact_acl(
            ref,
            actor_id=actor_id,
            project_id=project_id,
            action="read",
            granted_agents=grants,
        )
        if not acl.allowed:
            continue
        out.append(ref)
        if len(out) >= max(1, min(int(limit), 500)):
            break
    return out
