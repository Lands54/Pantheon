# 🏛️ Pantheon

[![Status](https://img.shields.io/badge/Status-Research_Preview-orange)](https://github.com/yourusername/pantheon)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**Pantheon** is an experimental platform for orchestrating **autonomous, file-grounded multi-agent simulations**. 

Unlike traditional chat-based agents, Pantheon agents ("Beings") inhabit a persistent filesystem territory, negotiate their own interaction protocols, and collaborate on complex tasks through a unique **Pulse-based** scheduling system.

---

## 🌟 Why Pantheon?

Most agent frameworks focus on transient, conversational tasks. Pantheon is built for **emergence** and **persistence**:

- **🌍 World Building**: Agents don't just chat; they build software, simulate ecosystems, and maintain long-term projects within isolated "World" directories.
- **📜 Protocol Negotiation**: Agents can autonomously draft, debate, and sign integration protocols (e.g., specific JSON schemas for API interaction) before executing code.
- **❤️ Pulse System**: Instead of infinite loops, agents operate on a discrete "Pulse" rhythm, allowing for deterministic debugging and precise resource control.
- **📂 Territorial Memory**: An agent's memory is not a vector database in the cloud—it is a markdown file in their local folder. If they can't read it, they don't know it.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [Conda](https://docs.conda.io/en/latest/) (Recommended)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/pantheon.git
   cd pantheon
   ```

2. **Set up the environment**
   ```bash
   conda create -n gods_env python=3.11
   conda activate gods_env
   pip install -r requirements.txt
   ```

3. **Initialize Configuration**
   ```bash
   # Sets up your local generic config
   cp config.example.json config.json
   # Generate a new world (project)
   ./temple.sh project create demo_world
   ```

4. **Launch the Server**
   Start the intention rendering engine (The Pulse):
   ```bash
   python server.py
   ```

---

## 📖 Core Concepts

### 1. The World (`Project`)
A **World** is a self-contained directory under `projects/`. It contains its own agents, configuration, and shared knowledge. Agents in one world cannot access another.

### 2. The Being (`Agent`)
An agent is an autonomous entity with:
- **Territory**: A dedicated folder for its code and memory.
- **Tools**: Capabilities to read/write files, execute commands, and communicate.
- **Directives**: High-level goals (e.g., "Designing a library system" or "Surviving as a Sheep").

### 3. The Protocol (`Negotiation`)
Agents use tools like `record_protocol` to formalize their interactions.
> *Example*: In the `animal_world_emergent` simulation, the **Sheep** and **Tiger** agents autonomously negotiated a `hunting_protocol`, agreeing on "detection range" and "energy cost" parameters without human hardcoding.

### 4. The Pulse (`Runtime`)
Pantheon uses a "Pulse" to wake up agents. A Pulse is a single execution cycle where an agent:
1. **Perceives** its inbox and file changes.
2. **Reasons** about its next step.
3. **Acts** (calls tools).
4. **Sleeps** until the next Pulse.

---

## 🛠️ Usage References

### CLI (`temple.sh`)

The `temple.sh` script is your divine scepter for controlling the simulation.

| Command | Description |
|---------|-------------|
| `./temple.sh project list` | Show all available worlds. |
| `./temple.sh project switch <name>` | Set the active world context. |
| `./temple.sh agent list` | List all living agents in the current world. |
| `./temple.sh confess --to <agent> "msg"` | Send a divine instruction (God mode). |
| `./temple.sh check inbox` | Read messages sent to you by agents. |

### Runtime Strategies

You can configure how agents think during a Pulse:

- **`strict_triad`**: The classic "Reason -> Act -> Stop" loop. Safe and predictable.
- **`iterative_action`**: Allows agents to chain multiple actions in one thought process.
- **`freeform`** *(Experimental)*: Unconstrained loop until the agent decides to stop.

```bash
# Set strategy for a project
./temple.sh --project demo_world config set phase.strategy iterative_action
```

### Hermes Protocol Bus (v0.1)

Pantheon now includes **Hermes**, a project-scoped protocol execution bus:

- Protocol registry per project (`projects/{project_id}/protocols/registry.json`)
- Sync/Async invocation
- Invocation audit log (`invocations.jsonl`)
- Async job status (`projects/{project_id}/protocols/jobs/*.json`)

Security default:
- `agent_tool` provider is **disabled by default**.
- Enable only when needed:
  `./temple.sh -p demo_world config set hermes.allow_agent_tool true`

Example:

```bash
# Register protocol
./temple.sh -p demo_world protocol register \
  --name grass.scan \
  --provider agent_tool \
  --agent grass \
  --tool list_dir

# Invoke sync
./temple.sh -p demo_world protocol call \
  --name grass.scan \
  --caller ground \
  --mode sync \
  --payload '{"path":"."}'

# Invoke async
./temple.sh -p demo_world protocol call \
  --name grass.scan \
  --caller ground \
  --mode async

# Register HTTP protocol (localhost only)
./temple.sh -p demo_world protocol register \
  --name bridge.echo \
  --provider http \
  --url http://127.0.0.1:9000/echo \
  --method POST \
  --request-schema '{"type":"object","required":["msg"],"properties":{"msg":{"type":"string"}}}' \
  --response-schema '{"type":"object","required":["result","status_code"],"properties":{"status_code":{"type":"integer"},"result":{"type":"object"}}}'

# Route by target agent + function id (Hermes(agent,function,payload))
./temple.sh -p demo_world protocol route \
  --target fire_god \
  --function check_fire_speed \
  --caller ground \
  --payload '{"wind":3.2}'

# Contract lifecycle
./temple.sh -p demo_world protocol contract-register --file contract.json
./temple.sh -p demo_world protocol contract-commit --title "Ecosystem Contract" --version 1.0.0 --agent tiger
./temple.sh -p demo_world protocol contract-resolve --title "Ecosystem Contract" --version 1.0.0

# Port lease management (avoid localhost port collisions)
./temple.sh -p demo_world protocol port-reserve --owner grass_api
./temple.sh -p demo_world protocol port-list
./temple.sh -p demo_world protocol port-release --owner grass_api
```

Python SDK:

```python
from gods.hermes.client import HermesClient

cli = HermesClient(base_url="http://localhost:8000")
ret = cli.route(
    project_id="demo_world",
    caller_id="ground_service",
    target_agent="fire_god",
    function_id="check_fire_speed",
    payload={"wind": 3.2},
)
print(ret)
```

Hermes-dominated Animal World demo:

```bash
python scripts/run_animal_world_hermes.py
```

Mnemosyne durable archives:

```bash
./temple.sh mnemosyne write --vault human --author overseer --title "exp-note" --content "step-1 completed" --tags "exp,run1"
./temple.sh mnemosyne list --vault human --limit 20
```

Project report helpers:

```bash
./temple.sh project report demo_world
./temple.sh project report-show demo_world
```

---

## 📂 Project Structure

```text
Pantheon/
├── api/               # FastAPI server & Pulse scheduler
├── cli/               # Command-line interface logic
├── gods/              # The Divine Core (Agent & Tool definitions)
│   ├── agents/        # Base agent logic (Brain, Memory)
│   ├── tools/         # Capabilities (Filesystem, Communication)
│   └── systems/       # Emergent systems (Protocol recording)
├── projects/          # User-created Worlds (The "Sandboxes")
│   └── animal_world/  # Example: An ecosystem simulation
├── frontend/          # (Optional) React-based observation deck
└── temple.sh          # Main entry point
```

---

## 🛡️ Safety & Security

- **Sandboxing**: Agents are restricted to their project directories, but `run_command` is powerful. Review code before running purely autonomous loops.
- **API Keys**: Stored in local `config.json` (git-ignored). `GET /config` returns redacted key only.
- **Deprecated Compatibility**: `legacy social api` and `simulation.parallel` remain for compatibility and are disabled/no-op by default.
- **Resource Limits**: The Pulse system prevents infinite loops by default, requiring explicit "wake up" signals or cron-like schedules.

---

## 🤝 Contributing

Pantheon is an experiment in **Structure-from-Chaos**. We welcome contributions that help agents collaborate more effectively!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

<p align="center">
  <i>"In the beginning was the Command Line."</i>
</p>
