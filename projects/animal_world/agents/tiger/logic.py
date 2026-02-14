def update(state):
    tiger = float(state.get("tiger", 5.0))
    sheep = float(state.get("sheep", 20.0))
    hunted = min(sheep * 0.25, tiger * 0.18)
    tiger_next = max(0.0, tiger + hunted * 0.05 - tiger * 0.06)
    state["tiger"] = tiger_next
    state["sheep"] = max(0.0, sheep - hunted)
    state["stats"]["tiger_hunt"] += hunted
