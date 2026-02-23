# 🧠 DrupalMind — Agentic AI Website Builder

<p align="center">
  <img src="https://img.shields.io/badge/Drupal-10+-0678BE?style=for-the-badge&logo=drupal" alt="Drupal 10">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Docker-Container-2496ED?style=for-the-badge&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/LLM-Anthropic%20%7C%20OpenAI%20%7C%20Ollama-F4A261?style=for-the-badge" alt="LLM Providers">
</p>

> Paste a URL. Watch AI agents build it in Drupal.

DrupalMind is a multi-agent AI system (v2) that takes a source website URL or natural language description and autonomously builds a matching Drupal 10 site — structure, content, theme, menus, and all.

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Environment Variables](#-environment-variables)
- [Services](#-services)
- [Project Structure](#-project-structure)
- [CLI Usage](#-cli-usage)
- [Development](#-development)
- [Documentation](#-documentation)
- [License](#-license)

---

## ✨ Features

- **Multi-LLM Support**: Use Anthropic Claude, OpenAI GPT-4, or Ollama (local)
- **Autonomous Agents**: AI-powered agents for analysis, building, theming, and content migration
- **Drupal 10 Integration**: Full JSON:API integration for content management
- **Real-time UI**: Live progress monitoring via WebSocket
- **Docker Ready**: Complete containerized deployment
- **Custom Endpoints**: Support for self-hosted LLM servers

### v2 New Features

| Feature | Description |
|---------|-------------|
| **Visual Feedback** | Playwright renders source and Drupal side-by-side with perceptual hash diff |
| **Payload Validator** | Validates JSON:API payloads before sending to Drupal |
| **ProbeAgent** | Empirical component discovery - tests every Drupal component via real API calls |
| **MappingAgent** | Confidence-scored mapping with fidelity estimates |
| **Refinement Loops** | Micro-loop (5 iterations) and Meso-loop for component refinement |
| **Gap Report** | Structured compromise list with before/after screenshots |
| **Cross-Migration Learning** | Global knowledge base accumulates successful patterns |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                           │
│              http://localhost:5510 (React + Nginx)              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                           │
│                    http://localhost:5511 (FastAPI)              │
│  ┌──────────────┬──────────────┬──────────────┬───────────────┐ │
│  │   Analyzer   │    Train     │   Mapping    │    Build      │ │
│  │    Agent     │    Agent     │    Agent     │    Agent      │ │
│  ├──────────────┼──────────────┼──────────────┼───────────────┤ │
│  │   Probe      │    Theme     │   Content    │   VisualDiff  │ │
│  │    Agent     │    Agent     │    Agent     │    Agent      │ │
│  ├──────────────┼──────────────┴──────────────┼───────────────┤ │
│  │     Test     │         QAAgent            │               │ │
│  └──────────────┴────────────────────────────┴───────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DRUPAL 10 + JSON:API                       │
│                      http://localhost:5500                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐     │
│  │   MySQL │  │  Redis  │  │  phpMy  │  │     Mailpit     │     │
│  │   8.0   │  │    7    │  │  Admin  │  │  (Email Test)  │     │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Pipeline

```
1. USER submits URL or description
         │
         ▼
2. ORCHESTRATOR creates build plan
         │
    ┌────┴────────────────────────────────────┐
    │              AGENTS                       │
    │  🔍 AnalyzerAgent  — scrape source       │
    │  📡 ProbeAgent    — probe Drupal         │
    │  📚 TrainAgent    — learn Drupal         │
    │  🗺️  MappingAgent — confidence scoring   │
    │  🏗️ BuildAgent   — build pages          │
    │  🎨 ThemeAgent   — match design          │
    │  📝 ContentAgent — migrate text          │
    │  👁️ VisualDiffAgent — compare renders   │
    │  🧪 TestAgent    — compare result       │
    │  ✅ QAAgent      — final checks          │
    └─────────────────────────────────────────┘
         │
         ▼
3. Drupal site live at localhost:5500
```

---

## 📌 Prerequisites

- **Docker Desktop** (Mac/Windows) or Docker Engine (Linux)
- **Git**
- **At least one LLM provider**:
  - [Anthropic API Key](https://console.anthropic.com) (for Claude)
  - [OpenAI API Key](https://platform.openai.com) (for GPT-4)
  - [Ollama](https://ollama.com) installed locally (for free local models)

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/TWeb79/29-DrupalMigrationAgent.git
cd 29-DrupalMigrationAgent
```

### 2. Configure Environment

```bash
cp .env_example .env
# Edit .env with your preferred LLM provider
```

### 3. Start Infrastructure (Drupal, Database, Redis)

```bash
docker compose --profile local-drupal up -d
```

Or start only the required services:

```bash
docker compose up -d drupal db phpmyadmin mailpit redis
```

### 4. Install Drupal

Open **http://localhost:5500** and run the installer:

| Field | Value |
|-------|-------|
| Database name | `drupal` |
| Username | `drupal` |
| Password | `drupalpass123` |
| Host *(Advanced)* | `db` |
| Port *(Advanced)* | `3306` |

### 5. Run Setup Script

```bash
# Copy script to container and run
docker cp scripts/setup-drupal.sh drupal:/tmp/setup-drupal.sh
docker exec -it drupal bash /tmp/setup-drupal.sh
```

### 6. Start Agents and UI

```bash
docker compose up -d drupalmind-agents drupalmind-ui
```

### 7. Open DrupalMind

Go to **http://localhost:5510** — paste a URL and click Start Build.

---

## ⚙️ Configuration

### LLM Provider Options

#### Option A: Anthropic Claude (Default)

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
# Optional: Use custom endpoint
ANTHROPIC_BASE_URL=https://api.anthropic.com
AGENT_MODEL=claude-sonnet-4-20250514
```

#### Option B: OpenAI GPT-4

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
# Optional: Use custom endpoint (e.g., Azure OpenAI, proxy)
OPENAI_BASE_URL=https://api.openai.com/v1
```

#### Option C: Ollama (Local/Free)

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3  # or deepseek-r1, mistral, etc.
```

To start Ollama with Docker:

```bash
docker compose --profile ollama up -d ollama
```

---

## 📝 Environment Variables

### LLM Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider: `anthropic`, `openai`, or `ollama` | `anthropic` |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `ANTHROPIC_BASE_URL` | Custom Anthropic endpoint | `https://api.anthropic.com` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `OPENAI_BASE_URL` | Custom OpenAI endpoint | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name | `llama3` |
| `AGENT_MODEL` | Model name for agents | varies by provider |

### Drupal Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DRUPAL_API_URL` | Drupal site URL | `http://drupal` |
| `DRUPAL_API_USER` | Drupal API username | `apiuser` |
| `DRUPAL_API_PASS` | Drupal API password | `apiuser` |

### Agent Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection URL | `redis://redis:6379` |
| `AGENT_MAX_RETRIES` | Max retries for agent actions | `3` |
| `AGENT_LOG_LEVEL` | Log level: `debug`, `info`, `warning` | `info` |

### v2 Quality Thresholds

| Variable | Description | Default |
|----------|-------------|---------|
| `SIMILARITY_THRESHOLD` | Visual diff threshold | `0.85` |
| `MIN_SIMILARITY_THRESHOLD` | Minimum acceptable similarity | `0.30` |
| `MAX_MICRO_ITERATIONS` | Max iterations per component | `5` |
| `MAX_MESO_ITERATIONS` | Max iterations per page | `3` |
| `MAX_BUILD_RETRIES` | Max build retry attempts | `2` |

### v2 Feature Flags

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_VISUAL_DIFF` | Enable visual diff comparisons | `true` |
| `ENABLE_MISSING_PIECE_DETECTION` | Enable gap detection | `true` |
| `ENABLE_GAP_REPORT` | Generate gap reports | `true` |
| `ENABLE_HUMAN_REVIEW` | Enable human review gate | `true` |
| `DEBUG_MODE` | Enable debug logging | `false` |

---

## 🐳 Services

| Service | URL | Description |
|---------|-----|-------------|
| **Drupal 10** | http://localhost:5500 | Main Drupal site |
| **Drupal Admin** | http://localhost:5500/user/login | Drupal administration |
| **JSON:API** | http://localhost:5500/jsonapi | Drupal REST API |
| **phpMyAdmin** | http://localhost:5501 | Database management |
| **Mailpit** | http://localhost:5502 | Email testing UI |
| **SMTP** | localhost:5503 | Email testing SMTP |
| **DrupalMind UI** | http://localhost:5510 | Agent control panel |
| **Agent API** | http://localhost:5511 | REST API for agents |
| **Redis** | localhost:5520 | Memory/state store |
| **Ollama** | http://localhost:11434 | Local LLM (optional) |

---

## 📂 Project Structure

```
drupal-mind/
├── agents/                    # AI Agent runtime
│   ├── base_agent.py          # Base agent with LLM support
│   ├── orchestrator.py        # Main orchestration agent
│   ├── analyzer.py            # Source site analyzer
│   ├── probe_agent.py         # Drupal component prober
│   ├── mapping_agent.py       # Confidence-scored mapping
│   ├── build_agent.py         # Drupal builder
│   ├── train_agent.py         # Drupal knowledge trainer
│   ├── theme_agent.py         # Theme application
│   ├── content_agent.py       # Content migration
│   ├── test_agent.py          # Comparison testing
│   ├── qa_agent.py            # Quality assurance
│   ├── visual_diff_agent.py   # Visual comparison
│   ├── agents.py              # Agent utility functions
│   ├── memory.py              # Redis-backed memory
│   ├── drupal_client.py       # Drupal JSON:API client
│   ├── config.py              # Configuration loader
│   ├── main.py                # FastAPI server
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile            # Agent container image
│
├── ui/                        # React UI (static files)
│   ├── index.html             # Entry HTML
│   ├── DrupalMindUI.jsx      # Main React component
│   ├── nginx.conf             # Nginx configuration
│   ├── package.json          # Node dependencies
│   └── Dockerfile             # UI container image
│
├── scripts/                   # Setup scripts
│   ├── setup-drupal.sh       # Drupal configuration
│   └── setup.ps1             # Windows setup
│
├── plans/                     # Planning documents
│   └── v2_changes_summary.md # v2 feature summary
│
├── docker-compose.yml         # Main compose file
├── docker-compose_freshinstall.yml  # Fresh installation template
├── run_migration.py          # CLI migration tool
├── README.md                 # This file
├── CONCEPT.md               # Detailed architecture
├── Version2.md              # v2 feature details
├── DrupalInstallation.md    # Installation guide
├── DrupalConnection.md      # Connection details
├── .env_example            # Environment template
└── .gitignore              # Git ignore rules
```

---

## 💻 CLI Usage

The CLI tool allows running migrations from the command line with detailed debug output.

### Basic Usage

```bash
# Run migration for a URL
python run_migration.py http://example.com/

# With verbose output
python run_migration.py http://example.com/ --verbose
```

### Requirements

```bash
# Install CLI dependencies
pip install -r requirements_cli.txt

# Set environment variables
set OPENAI_API_KEY=your-api-key
# or
set ANTHROPIC_API_KEY=your-api-key
```

---

## 🔧 Development

### Building Images

```bash
# Build all images
docker compose build

# Build specific service
docker compose build drupalmind-agents
docker compose build drupalmind-ui
```

### Running Services

```bash
# Start all services
docker compose up -d

# Start with local Drupal
docker compose --profile local-drupal up -d

# Start with Ollama
docker compose --profile ollama up -d

# View logs
docker compose logs -f drupalmind-agents
docker compose logs -f drupalmind-ui
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/build` | POST | Start a new build job |
| `/build/{job_id}` | GET | Get job status |
| `/jobs` | GET | List all jobs |
| `/memory` | GET | List memory keys |
| `/memory/{key}` | GET | Get memory value |
| `/memory/reset` | DELETE | Reset memory |
| `/ws` | WebSocket | Real-time progress stream |

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [DrupalInstallation.md](DrupalInstallation.md) | Step-by-step installation guide |
| [CONCEPT.md](CONCEPT.md) | Detailed agent architecture |
| [Version2.md](Version2.md) | v2 new features detailed |

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ❤️ for Drupal and AI
</p>
