# 🧠 DrupalMind — Agentic AI Website Builder (In Development)

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

- [� Management Summary](#-management-summary)
  - [What is DrupalMind?](#what-is-drupalmind)
  - [Core Process (11 Phases)](#core-process-11-phases)
  - [Three-Loop System (v2)](#three-loop-system-v2)
  - [Quality Features](#quality-features)
  - [Technology Stack](#technology-stack)
- [🤖 Agent Documentation](#-agent-documentation)
  - [Agent Pipeline Overview](#agent-pipeline-overview)
  - [1. ProbeAgent](#1-probeagent--empirical-component-discovery)
  - [2. AnalyzerAgent](#2-analyzeragent--source-site-analysis)
  - [3. TrainAgent](#3-trainagent--drupal-knowledge)
  - [4. MappingAgent](#4-mappingagent--component-mapping)
  - [5. BuildAgent](#5-buildagent--page-creation)
  - [6. ThemeAgent](#6-themeagent--design-application)
  - [7. ContentAgent](#7-contentagent--content-migration)
  - [8. VisualDiffAgent](#8-visualdiffagent--visual-comparison)
  - [9. TestAgent](#9-testagent--comparison-tests)
  - [10. QAAgent](#10-qaagent--quality-assurance)
  - [OrchestratorAgent](#orchestratoragent--coordination)
- [🔄 Detailed Process Flow](#-detailed-process-flow)
  - [Preparation Phase](#preparation-phase)
  - [Migration Phase](#migration-phase)
  - [Review Phase](#review-phase)
  - [Monitoring](#monitoring)
- [✨ Features](#-features)
- [🏗️ Architecture](#-architecture)
- [📌 Prerequisites](#-prerequisites)
- [🚀 Quick Start](#-quick-start)
- [⚙️ Configuration](#-configuration)
- [📝 Environment Variables](#-environment-variables)
- [🐳 Services](#-services)
- [📂 Project Structure](#-project-structure)
- [💻 CLI Usage](#-cli-usage)
- [🔧 Development](#-development)
- [📖 Documentation](#-documentation)
- [📄 License](#-license)

---

## 📊 Management Summary

### What is DrupalMind?

DrupalMind is an AI-powered migration system that analyzes a source website and automatically creates a Drupal 10 site. The system uses multiple specialized AI agents that work together to migrate structure, design, and content.

### Core Process (11 Phases)

| Phase | Agent | Description |
|-------|-------|-------------|
| 1 | **ProbeAgent** | Tests Drupal components empirically via API |
| 2 | **AnalyzerAgent** | Scrapes and analyzes the source site |
| 3 | **TrainAgent** | Learns available Drupal components |
| 4 | **MappingAgent** | Maps source elements to Drupal components |
| 5 | **BuildAgent** | Creates pages with refinement loops |
| 6 | **ThemeAgent** | Applies design tokens and CSS |
| 7 | **ContentAgent** | Migrates text and media content |
| 8 | **TestAgent** | Compares result with source |
| 9 | **QAAgent** | Performs quality checks |
| 10 | **Review** | Human review gate |
| 11 | **Publish** | Publication + learning capture |

### Three-Loop System (v2)

- **Micro-Loop**: Single component, max 5 iterations
- **Meso-Loop**: Full page, until threshold reached
- **Macro-Loop**: All migrations, permanently collects learnings

### Quality Features

| Feature | Description |
|---------|-------------|
| Visual Diff | Playwright renders source & Drupal, calculates perceptual hash similarity |
| Payload Validator | Validates JSON:API payloads before sending |
| Gap Report | List of all compromises with fidelity scores |
| Cross-Migration Learning | Global knowledge base for successful patterns |

### Technology Stack

- **Frontend**: React + Nginx (Port 5510)
- **Backend**: FastAPI + Python 3.12 (Port 5511)
- **Database**: MySQL 8.0 + Redis 7
- **LLM**: Anthropic Claude, OpenAI GPT-4, or Ollama
- **Testing**: Playwright for visual comparisons

---

## 🤖 Agent Documentation

### Agent Pipeline Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Probe     │───▶│  Analyzer   │───▶│   Train     │───▶│  Mapping    │
│   Agent     │    │   Agent     │    │   Agent     │    │   Agent     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                                                    │
       │                                                    ▼
       │                                           ┌─────────────┐
       │                                           │   Build     │
       │                                           │   Agent     │◀────┐
       │                                           └─────────────┘     │
       │                                                  │            │
       ▼                                                  ▼            │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┤
│   Theme     │    │  Content    │    │   Visual    │    │   Test      │
│   Agent     │    │   Agent     │    │    Diff     │    │   Agent     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                  │
                                                                  ▼
                                                           ┌─────────────┐
                                                           │     QA      │
                                                           │   Agent     │
                                                           └─────────────┘
```

---

### 1. ProbeAgent — Empirical Component Discovery

**File**: [`agents/probe_agent.py`](agents/probe_agent.py)

| Property | Value |
|------------|------|
| Phase | 1 - Probe |
| Main Role | Tests Drupal components through real API calls |
| Output | Capability Envelopes in Redis |

**Tasks:**
- Tests each Drupal component through real API calls
- Discovers which fields and parameters are accepted
- Documents errors and successes
- Builds verified "capability envelopes" for each component

**High-Level Prompt:**
```
You are the ProbeAgent for DrupalMind. Your job is to:
1. Test Drupal components by making real API calls
2. Discover what fields and parameters are actually accepted
3. Document what causes errors vs success
4. Build a verified "capability envelope" for each component

For each component you probe:
- Try creating a minimal node with just required fields
- Try adding optional fields one by one
- Test edge cases (empty values, max lengths, special characters)
- Document the exact payload that succeeded or failed
- Record error messages so other agents can avoid mistakes

Store results as capability envelopes in memory under key "capability_envelopes/{component_name}".
```

---

### 2. AnalyzerAgent — Source Site Analysis

**File**: [`agents/analyzer.py`](agents/analyzer.py)

| Property | Value |
|------------|------|
| Phase | 2 - Discovery |
| Main Role | Scrapes and analyzes the source site |
| Output | Site Blueprint with design tokens, navigation, pages |

**Tasks:**
- Scrapes source URL or analyzes descriptions
- Extracts design tokens (colors, fonts)
- Captures navigation and page structure
- Creates reference screenshots for VisualDiff

**Usage:**
```python
analyzer = AnalyzerAgent()
blueprint = await analyzer.analyze(source_url, mode="url")
```

---

### 3. TrainAgent — Drupal Knowledge

**File**: [`agents/train_agent.py`](agents/train_agent.py)

| Property | Value |
|------------|------|
| Phase | 3 - Knowledge |
| Main Role | Loads Drupal component knowledge for other agents |
| Output | Formatted knowledge for downstream agents |

**Tasks:**
- Reads Capability Envelopes from ProbeAgent
- Formats knowledge for downstream agents
- Provides component knowledge via tools

**High-Level Prompt:**
```
You are the TrainAgent for DrupalMind. Your job is to:
1. Read capability envelopes from ProbeAgent (key: "capability_envelopes/*")
2. Format this knowledge for downstream agents
3. Make the component knowledge easily accessible via tools

The capability envelopes contain verified information about what each component
can actually do - discovered through empirical testing by ProbeAgent.
```

---

### 4. MappingAgent — Component Mapping

**File**: [`agents/mapping_agent.py`](agents/mapping_agent.py)

| Property | Value |
|------------|------|
| Phase | 4 - Mapping |
| Main Role | Maps source elements to Drupal components |
| Output | Mapping Manifest with confidence scores |

**Tasks:**
- Reads Site Blueprint and Capability Envelopes
- Maps each source element to the best Drupal component
- Assigns confidence scores (0-1) and fidelity estimates
- Flags low-confidence items for human review
- Creates mapping manifest for BuildAgent

**High-Level Prompt:**
```
You are the MappingAgent for DrupalMind. Your job is to:
1. Read the site blueprint (source elements)
2. Read capability envelopes from ProbeAgent (what Drupal can do)
3. Read global knowledge base (past successful mappings)
4. Map each source element to the best available Drupal component
5. Assign confidence scores (0-1) and fidelity estimates
6. Flag low-confidence items for human review
7. Produce a mapping manifest for BuildAgent

For each source element, determine:
- Best matching Drupal component
- Confidence score (high: >0.8, medium: 0.5-0.8, low: <0.5)
- Any compromises needed (e.g., "no image carousel available, will use grid")
- Whether human review is needed

Store the mapping manifest in memory under key "mapping_manifest".
```

---

### 5. BuildAgent — Page Creation

**File**: [`agents/build_agent.py`](agents/build_agent.py)

| Property | Value |
|------------|------|
| Phase | 5 - Build |
| Main Role | Creates Drupal pages based on blueprint |
| Output | Created pages, menu items |

**Tasks:**
- Reads Site Blueprint and Mapping Manifest
- Creates pages in Drupal via JSON:API
- Implements payload validator (prevents unsafe HTML)
- Runs micro-loop (max 5 iterations per component)
- Runs meso-loop (page refinement)
- Integrates VisualDiffAgent after each placement

**High-Level Prompt:**
```
You are the BuildAgent for DrupalMind, an AI system that builds Drupal websites.

Your job is to build a Drupal site based on the Site Blueprint and Mapping Manifest.

PROCESS:
1. Read the site blueprint from memory (key: "site_blueprint")
2. Read the mapping manifest (key: "mapping_manifest")
3. Read available component knowledge (key: "capability_envelopes/*")
4. For each page in the blueprint, create it in Drupal using the appropriate API calls
5. Use payload validator before sending any content to Drupal
6. Create navigation menu items for the main menu
7. Report what you've built

RULES:
- Create ONE page per task
- Use "basic_html" format for body fields unless full_html available
- For hero sections, include a prominent heading in the body HTML
- For navigation, use the "main" menu
- Always set status: true to publish content
- ALWAYS validate payloads before sending to Drupal
```

---

### 6. ThemeAgent — Design Application

**File**: [`agents/agents.py`](agents/agents.py:39)

| Property | Value |
|------------|------|
| Phase | 6 - Theme |
| Main Role | Applies design tokens and CSS |
| Output | Custom Theme Block in Drupal |

**Tasks:**
- Reads design tokens from AnalyzerAgent
- Generates CSS based on colors and fonts
- Creates custom block with CSS in Drupal
- Applies structured CSS to the theme

**Usage:
```python
theme_agent = ThemeAgent()
result = await theme_agent.apply_theme()
```

---

### 7. ContentAgent — Content Migration

**File**: [`agents/agents.py`](agents/agents.py:202)

| Property | Value |
|------------|------|
| Phase | 7 - Content |
| Main Role | Migrates text and media content |
| Output | Migrated content in Drupal |

**Tasks:**
- Reads Site Blueprint with sections
- Reads capability envelopes for field-level constraints
- Migrates all section types (blog, team, testimonials, content, features, etc.)
- Uses component templates for structured content
- Handles images and media

**v2 Features:**
- Uses capability envelopes for field-level constraints
- Uses component templates for structured content

---

### 8. VisualDiffAgent — Visual Comparison

**File**: [`agents/visual_diff_agent.py`](agents/visual_diff_agent.py)

| Property | Value |
|------------|------|
| Phase | 8 (after Build) - Visual Diff |
| Main Role | Renders and compares source & Drupal visually |
| Output | Similarity Score, Refinement Instructions |

**Tasks:**
- Renders source URL and Drupal page with Playwright
- Computes perceptual hash similarity (0-1)
- Identifies regions with significant differences
- Generates actionable refinement instructions
- Stores diff results for gap report

**High-Level Prompt:**
```
You are the VisualDiffAgent for DrupalMind. Your job is to:
1. Render both source URL and Drupal page using Playwright
2. Compute perceptual hash similarity between the two renders
3. Identify regions with significant differences
4. Generate actionable refinement instructions for BuildAgent
5. Store diff results in memory for the gap report

The similarity score ranges from 0 (completely different) to 1 (identical).
Scores above 0.85 are considered acceptable.
```

---

### 9. TestAgent — Vergleichstests

**File**: [`agents/agents.py`](agents/agents.py:428)

| Property | Value |
|------------|------|
| Phase | 8 - Verify |
| Main Role | Compares result with source specification |
| Output | Test report with score |

**Tasks:**
- Checks if site blueprint exists
- Verifies if pages were created
- Checks navigation (menu items)
- Compares with source specification
- Calculates overall match score

**Usage:**
```python
test_agent = TestAgent()
result = await test_agent.run_tests()
```

---

### 10. QAAgent — Quality Assurance

**File**: [`agents/agents.py`](agents/agents.py:529)

| Property | Value |
|------------|------|
| Phase | 9 - QA |
| Main Role | Final quality checks and Gap Report |
| Output | QA Report + Gap Report |

**Tasks:**
- Performs accessibility checks
- Checks links and performance
- Generates gap report with all compromises
- Calculates fidelity scores
- Writes cross-migration learnings to global knowledge base
- Flags items for human review

**Gap Report Structure:**
```json
{
  "items": [
    {
      "element_type": "hero",
      "source_type": "hero_with_cta",
      "component_used": "hero_basic",
      "fidelity_score": 0.85,
      "compromises": ["No animated CTA available"]
    }
  ],
  "average_fidelity": 0.87,
  "requires_review": true
}
```

---

### OrchestratorAgent — Coordination

**File**: [`agents/orchestrator.py`](agents/orchestrator.py)

| Property | Value |
|------------|------|
| Phases | 10 (Review), 11 (Publish) |
| Main Role | Coordinates all agents, manages build plan |

**Tasks:**
- Creates build plan with 11 phases
- Dispatches to specialized agents
- Streams progress events via WebSocket
- Manages human review gate
- Summarizes results and publishes

---

## 🔄 Detailed Process Flow

### Preparation Phase

1. **Start System**
   ```bash
   docker compose up -d drupal db phpmyadmin mailpit redis
   ```
   
2. **Drupal Installation**
   - Web installer at http://localhost:5500
   - Database: `drupal` / User: `drupal` / Pass: `drupalpass123`
   
3. **Run Setup Script**
   ```bash
   docker cp scripts/setup-drupal.sh drupal:/tmp/
   docker exec -it drupal bash /tmp/setup-drupal.sh
   ```
   
4. **Start Agents**
   ```bash
   docker compose up -d drupalmind-agents drupalmind-ui
   ```

### Migration Phase

1. **Enter URL** in DrupalMind UI (http://localhost:5510)
2. **Orchestrator** creates build plan and starts pipeline
3. **Agent Loop** runs through all 11 phases
4. **Real-time progress** via WebSocket

### Review Phase

1. **Gap Report** shows all compromises
2. **Visual Diff** shows before/after comparison
3. **Human Review Gate** - approval required
4. **Publish** - go live

### Monitoring

```bash
# View logs
docker compose logs -f drupalmind-agents

# Check Redis contents
docker exec -it redis redis-cli
> KEYS *

# API status
curl http://localhost:5511/health
```

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
