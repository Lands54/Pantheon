import json
import importlib.util
from pathlib import Path


def load_update(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.update


def main():
    base = Path(__file__).resolve().parents[1]
    sheep_update = load_update(base / "sheep" / "logic.py")
    tiger_update = load_update(base / "tiger" / "logic.py")
    grass_update = load_update(base / "grass" / "logic.py")
    ground_update = load_update(base / "ground" / "logic.py")

    state = {
        "sheep": 24.0,
        "tiger": 5.0,
        "grass": 135.0,
        "soil": 82.0,
        "stats": {
            "sheep_food_intake": 0.0,
            "tiger_hunt": 0.0,
            "grass_growth": 0.0,
            "soil_regen": 0.0,
        },
    }
    history = []
    for step in range(1, 81):
        grass_update(state)
        sheep_update(state)
        tiger_update(state)
        ground_update(state)

        # floor values
        for key in ("sheep", "tiger", "grass", "soil"):
            state[key] = round(max(0.0, state[key]), 4)

        snapshot = {
            "step": step,
            "sheep": state["sheep"],
            "tiger": state["tiger"],
            "grass": state["grass"],
            "soil": state["soil"],
        }
        history.append(snapshot)

    report = {
        "steps": len(history),
        "final_state": history[-1],
        "history_tail": history[-10:],
        "stats": state["stats"],
    }
    out = Path(__file__).resolve().parent / "animal_world_output.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["final_state"], ensure_ascii=False))


if __name__ == "__main__":
    main()
