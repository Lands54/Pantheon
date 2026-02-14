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
   python -m api.server
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
- **API Keys**: Stored in `config.json` (git-ignored). Never commit your keys.
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
