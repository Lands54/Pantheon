def update(state):
    soil = float(state.get("soil", 80.0))
    grass = float(state.get("grass", 120.0))
    sheep = float(state.get("sheep", 20.0))
    tiger = float(state.get("tiger", 5.0))
    pressure = sheep * 0.015 + tiger * 0.01
    regen = grass * 0.012
    soil_next = max(10.0, min(140.0, soil + regen - pressure))
    state["soil"] = soil_next
    state["stats"]["soil_regen"] += (soil_next - soil)
