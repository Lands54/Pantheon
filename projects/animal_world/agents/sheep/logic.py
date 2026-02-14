def update(state):
    sheep = float(state.get("sheep", 20.0))
    grass = float(state.get("grass", 120.0))
    eaten = min(grass, sheep * 0.25)
    sheep_next = max(0.0, sheep + eaten * 0.07 - sheep * 0.03)
    state["sheep"] = sheep_next
    state["grass"] = max(0.0, grass - eaten)
    state["stats"]["sheep_food_intake"] += eaten
