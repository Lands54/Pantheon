def update(state):
    grass = float(state.get("grass", 120.0))
    soil = float(state.get("soil", 80.0))
    growth = max(0.8, 2.2 + soil * 0.04 - grass * 0.01)
    state["grass"] = max(0.0, grass + growth)
    state["stats"]["grass_growth"] += growth
