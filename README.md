# Gods Platform

A distributed multi-agent platform where AI agents exist as autonomous entities with isolated territories, persistent memory, and social interaction capabilities.

## Architecture

Gods Platform follows a clean three-layer architecture:

- **Core Layer (`gods/`)**: Business logic, agents, tools, and workflows
- **API Layer (`api/`)**: FastAPI server with modularized routes
- **CLI Layer (`cli/`)**: Command-line interface for management

## Quick Start

### 1. Install Dependencies

```bash
conda create -n gods_env python=3.11
conda activate gods_env
pip install -r requirements.txt
```

### 2. Set API Key

```bash
python cli/main.py init YOUR_OPENROUTER_API_KEY
```

### 3. Start Server

```bash
python api/server.py
```

### 4. Access Web UI

Open `http://localhost:8000` in your browser.

### 5. Use CLI

```bash
# List agents
python cli/main.py list

# Create a new world
python cli/main.py project create my_world

# Broadcast to all agents
python cli/main.py broadcast "Hello, divine beings!"

# Run automated tests
python cli/main.py test --cleanup
```

## Project Structure

```
Gods/
├── gods/                  # Core business logic
│   ├── config.py          # Configuration management
│   ├── state.py           # State definitions
│   ├── workflow.py        # LangGraph workflows
│   ├── agents/            # Agent logic
│   │   ├── base.py        # GodAgent class
│   │   └── brain.py       # LLM interface
│   └── tools/             # Agent capabilities
│       ├── communication.py
│       ├── filesystem.py
│       └── execution.py
│
├── api/                   # FastAPI server
│   ├── server.py          # Main server
│   ├── models.py          # Pydantic models
│   └── routes/            # Modularized endpoints
│       ├── config.py
│       ├── projects.py
│       ├── agents.py
│       └── communication.py
│
├── cli/                   # Command-line interface
│   ├── main.py            # CLI entry point
│   ├── utils.py           # Helper functions
│   └── commands/          # Command modules
│
├── tests/                 # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── frontend/              # React web UI
├── projects/              # Multi-project data
└── docs/                  # Documentation
```

## Key Features

- **Multi-Project Architecture**: Isolated worlds with independent agent ecosystems
- **Autonomous Agents**: Self-aware entities with persistent memory
- **Territory Isolation**: Each agent operates in a sandboxed file system
- **Social Simulation**: Agents communicate via inbox/broadcast mechanisms
- **Streaming Debates**: Real-time multi-agent conversations
- **Web + CLI**: Dual interface for management and interaction

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Quick Start Guide](docs/QUICKSTART.md)
- [API Documentation](docs/api.md)

## License

MIT
