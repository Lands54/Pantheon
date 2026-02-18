from __future__ import annotations

from gods.chaos.contracts import ResourceSnapshot


def test_snapshot_update_merges_dict_fields():
    s1 = ResourceSnapshot(project_id="p", agent_id="a", strategy="react_graph", runtime_meta={"x": 1})
    s2 = s1.update(runtime_meta={"y": 2})
    assert s1.runtime_meta == {"x": 1}
    assert s2.runtime_meta == {"x": 1, "y": 2}


def test_snapshot_update_replaces_list_fields():
    s1 = ResourceSnapshot(project_id="p", agent_id="a", strategy="react_graph", tool_catalog=["a"])
    s2 = s1.update(tool_catalog=["b", "c"])
    assert s1.tool_catalog == ["a"]
    assert s2.tool_catalog == ["b", "c"]


def test_snapshot_update_rejects_unknown_field():
    s1 = ResourceSnapshot(project_id="p", agent_id="a", strategy="react_graph")
    try:
        s1.update(not_exists=1)
    except ValueError as e:
        assert "unknown ResourceSnapshot field" in str(e)
        return
    raise AssertionError("expected ValueError")


def test_snapshot_patch_path_nested_dict():
    s1 = ResourceSnapshot(
        project_id="p",
        agent_id="a",
        strategy="react_graph",
        runtime_meta={"node": {"phase": "build_context"}},
    )
    s2 = s1.patch_path("runtime_meta.node.phase", "dispatch_tools")
    assert s1.runtime_meta["node"]["phase"] == "build_context"
    assert s2.runtime_meta["node"]["phase"] == "dispatch_tools"


def test_snapshot_patch_paths_support_list_index():
    s1 = ResourceSnapshot(
        project_id="p",
        agent_id="a",
        strategy="react_graph",
        tool_catalog=["a", "b"],
    )
    s2 = s1.patch_paths({"tool_catalog[1]": "c"})
    assert s1.tool_catalog == ["a", "b"]
    assert s2.tool_catalog == ["a", "c"]
