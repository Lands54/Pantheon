# Pantheon

Pantheon is an experimental multi-agent simulation platform for autonomous, file-grounded software collaboration.

Each agent ("Being") has its own territory, local memory, and tool access.  
Projects are isolated worlds, orchestrated by pulse-based scheduling through API + CLI.

## Status

This repository is in **research preview** stage:

- Architecture and orchestration are functional.
- Agent behavior is still unstable for long, fully autonomous tasks.
- Expect breaking changes.

## Core Concepts

- **World (`project`)**: isolated runtime and data space under `projects/<id>/`
- **Being (`agent`)**: autonomous actor with its own filesystem territory
- **Pulse**: scheduler-triggered activation cycle
- **Private channel**: `confess` / `send_message`
- **Protocol logging**: `record_protocol` emits structured negotiation events

## Architecture

- **Core** (`gods/`): agents, tools, runtime strategies, memory flow
- **API** (`api/`): FastAPI routes + scheduler
- **CLI** (`cli/`): operational control and diagnostics
- **Frontend** (`frontend/`): optional web console

## Quick Start

```bash
conda create -n gods_env python=3.11
conda activate gods_env
pip install -r requirements.txt
```

Set API key:

```bash
./temple.sh init YOUR_OPENROUTER_API_KEY
```

Start server:

```bash
python -m api.server
```

Basic CLI flow:

```bash
./temple.sh project create demo_world
./temple.sh project switch demo_world
./temple.sh list
./temple.sh project start demo_world
./temple.sh check genesis
```

## Runtime Strategies

- `strict_triad`: Reason -> Act -> Observe
- `iterative_action`: Reason + multiple Act/Observe loops
- `freeform`: unconstrained agent<->tool loop (experimental)

Set strategy per project:

```bash
./temple.sh --project demo_world config set phase.strategy freeform
```

## Tooling Surface

Agents can use tools for:

- communication (`check_inbox`, `send_message`, `send_to_human`)
- filesystem edits (`read_file`, `write_file`, `replace_content`, `insert_content`, `multi_replace`, `list_dir`)
- command execution (`run_command`)
- coordination (`record_protocol`, `list_agents`, `post_to_synod`, `abstain_from_synod`, `finalize`)

## Safety Notes

- Do **not** commit secrets (`config.json` is ignored).
- Rotate keys immediately if exposed.
- `run_command` is resource-guarded but still powerful; use cautiously.

## Project Layout

```text
gods/        core runtime
api/         FastAPI + scheduler
cli/         command-line control
tests/       unit/integration/e2e tests
projects/    runtime worlds (local, not for versioned test data)
```

## Roadmap

- executable inter-agent protocol registry
- contract-based cross-agent calls
- stronger convergence controls for autonomous loops
- better cost/runtime observability

## License

MIT
