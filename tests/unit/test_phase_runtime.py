from types import SimpleNamespace

from gods.agents.phase_runtime import AgentPhaseRuntime, PhaseToolPolicy, _base_phases


def test_phase_policy_blocks_disallowed_tool():
    policy = PhaseToolPolicy(
        phase_allow_map={"discover": {"list_dir", "read_file"}},
        disabled_tools=set(),
        max_repeat_same_call=2,
        explore_budget=3,
    )
    reason = policy.check("discover", "write_file", {"path": "a.txt"})
    assert reason is not None
    assert "not allowed" in reason


def test_phase_policy_blocks_repeated_same_call():
    policy = PhaseToolPolicy(
        phase_allow_map={"implement": {"read_file"}},
        disabled_tools=set(),
        max_repeat_same_call=2,
        explore_budget=10,
    )
    args = {"path": "x.py"}
    assert policy.check("implement", "read_file", args) is None
    policy.record("read_file", args)
    assert policy.check("implement", "read_file", args) is None
    policy.record("read_file", args)
    reason = policy.check("implement", "read_file", args)
    assert reason is not None
    assert "Repeated call blocked" in reason


def test_phase_policy_blocks_explore_budget():
    policy = PhaseToolPolicy(
        phase_allow_map={"discover": {"list_dir", "read_file"}},
        disabled_tools=set(),
        max_repeat_same_call=5,
        explore_budget=1,
    )
    assert policy.check("discover", "list_dir", {"path": "."}) is None
    policy.record("list_dir", {"path": "."})
    reason = policy.check("discover", "read_file", {"path": "a.txt"})
    assert reason is not None
    assert "budget" in reason.lower()


def test_next_phase_transitions_with_successful_run_command():
    dummy_agent = SimpleNamespace(project_id="default", agent_id="genesis")
    runtime = AgentPhaseRuntime(dummy_agent)
    phases = _base_phases()

    # implement -> verify on successful run_command
    idx = 1
    idx2 = runtime._next_phase_index(idx, phases, "run_command", "Manifestation Result (exit=0):")
    assert phases[idx2].name == "verify"

    # verify -> finalize on successful run_command
    idx = 2
    idx2 = runtime._next_phase_index(idx, phases, "run_command", "Manifestation Result (exit=0):")
    assert phases[idx2].name == "finalize"
