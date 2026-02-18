"""ACL decisions for Mnemosyne artifact access."""
from __future__ import annotations

from gods.mnemosyne.artifact_contracts import ArtifactACLDecision, ArtifactRef


def evaluate_artifact_acl(
    ref: ArtifactRef,
    *,
    actor_id: str,
    project_id: str,
    action: str,
    granted_agents: set[str] | None = None,
) -> ArtifactACLDecision:
    actor = str(actor_id or "").strip()
    target_project = str(project_id or "").strip()
    op = str(action or "read").strip().lower()

    if op not in {"read", "write"}:
        return ArtifactACLDecision(False, f"invalid action '{op}'")

    if ref.scope == "global":
        if op == "read":
            return ArtifactACLDecision(True, "")
        if actor in {"system", "human"}:
            return ArtifactACLDecision(True, "")
        return ArtifactACLDecision(False, "global scope write requires system/human")

    if ref.scope == "project":
        if ref.project_id != target_project:
            return ArtifactACLDecision(False, "cross-project access denied")
        return ArtifactACLDecision(True, "")

    if ref.scope == "agent":
        if ref.project_id != target_project:
            return ArtifactACLDecision(False, "cross-project access denied")
        grants = set([str(x).strip() for x in list(granted_agents or set()) if str(x).strip()])
        if actor in {"system", "human", ref.owner_agent_id}:
            return ArtifactACLDecision(True, "")
        if actor in grants:
            return ArtifactACLDecision(True, "")
        return ArtifactACLDecision(False, "agent scope only owner/system/granted-agent can access")

    return ArtifactACLDecision(False, f"invalid scope '{ref.scope}'")
