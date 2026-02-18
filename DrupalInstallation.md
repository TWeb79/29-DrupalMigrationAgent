# DrupalMind — Complete Installation Guide

> **End-to-end setup**: from zero to a fully running Drupal environment with the AI agent system connected and ready to build websites.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the Repository](#2-clone-the-repository)
3. [Configure Environment](#3-configure-environment)
4. [Start the Docker Stack](#4-start-the-docker-stack)
5. [Run the Drupal Web Installer](#5-run-the-drupal-web-installer)
6. [Automated Module Setup](#6-automated-module-setup)
7. [Enable JSON:API Write Access](#7-enable-jsonapi-write-access)
8. [Verify the API](#8-verify-the-api)
9. [Start the Agent System](#9-start-the-agent-system)
10. [Open the DrupalMind UI](#10-open-the-drupalmind-ui)
11. [Service Reference](#11-service-reference)
12. [Troubleshooting](#12-troubleshooting)
13. [Resetting Everything](#13-resetting-everything)

---

## 1. Prerequisites

You need the following installed on your machine before starting.

### Docker Desktop (Windows / macOS)

Download and install from: https://www.docker.com/products/docker-desktop/

After installing, open Docker Desktop and ensure it is **running** (whale icon in system tray).

Minimum recommended resources — set in Docker Desktop → Settings → Resources:
- CPU: 4 cores
- RAM: 4 GB
- Disk: 20 GB

### Docker Engine (Linux)

```bash
# Ubuntu / Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

### Git

```powershell
# Windows — download from https://git-scm.com/
# Or via winget:
winget install Git.Git
```

```bash
# macOS
brew install git

# Ubuntu / Debian
sudo apt install git
```

### Verify everything is ready

```powershell
docker --version
# Expected: Docker version 25.x.x or higher

docker compose version
# Expected: Docker Compose version v2.x.x or higher

git --version
# Expected: git version 2.x.x
```

---

## 2. Clone the Repository

```powershell
# Windows PowerShell
git clone https://github.com/YOUR_ORG/drupal-mind.git
cd drupal-mind
```

```bash
# macOS / Linux
git clone https://github.com/YOUR_ORG/drupal-mind.git
cd drupal-mind
```

Your directory should look like this:

```
drupal-mind/
├── docker-compose.yml       ← Main stack definition
├── .env.example             ← Environment template
├── .gitignore
├── DrupalInstallation.md    ← This file
├── README.md
├── scripts/
│   ├── setup.ps1            ← Windows one-click setup
│   ├── setup-drupal.sh      ← Module installer (runs inside container)
├── agents/                  ← Python agent system
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
└── ui/                      ← DrupalMind control panel
    └── Dockerfile
```

---

## 3. Configure Environment

Copy the environment template and add your API keys:

```powershell
# Windows
copy .env.example .env
notepad .env
```

```bash
# macOS / Linux
cp .env.example .env
nano .env
```

Edit these values in `.env`:

```env
# Required for agent AI — get from https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional — only needed if using GPT-4o as the agent model
OPENAI_API_KEY=sk-your-key-here
```

> **Security note:** The `.env` file is listed in `.gitignore` and will never be committed to Git. Never share it publicly.

---

## 4. Start the Docker Stack

Start only the core services first (Drupal, database, utilities). The agent containers come later.

```powershell
docker compose up -d drupal db phpmyadmin mailpit redis
```

You will see Docker pull the images on first run — this takes 2–5 minutes depending on your internet connection.

### Verify containers are running

```powershell
docker compose ps
```

Expected output:

```
NAME                 STATUS          PORTS
drupal               Up              0.0.0.0:5500->80/tcp
drupal_db            Up (healthy)    3306/tcp
drupal_phpmyadmin    Up              0.0.0.0:5501->80/tcp
drupal_mailpit       Up              0.0.0.0:5502->8025/tcp
drupal_redis         Up              0.0.0.0:5520->6379/tcp
```

> **Important:** Wait until `drupal_db` shows `Up (healthy)` before continuing. This takes about 30–60 seconds on first run.

If `drupal_db` shows `Up (health: starting)` wait another 15 seconds and re-run `docker compose ps`.

---

## 5. Run the Drupal Web Installer

Open your browser and go to: **http://localhost:5500**

The Drupal installer will start automatically.

### Step 1 — Choose language
Select **English** and click Save and continue.

### Step 2 — Choose installation profile
Select **Standard** and click Save and continue.

> Standard gives you Articles, Basic Pages, menus, blocks, and taxonomy out of the box — all required by the agent system.

### Step 3 — Database setup

Click **Advanced options** to expand the host/port fields.

| Field | Value |
|-------|-------|
| **Database type** | MySQL, MariaDB, Percona Server, or equivalent |
| **Database name** | `drupal` |
| **Database username** | `drupal` |
| **Database password** | `drupalpass123` |
| **Host** *(Advanced)* | `db` |
| **Port** *(Advanced)* | `3306` |

Click **Save and continue**.

> Drupal will now create all its database tables. This takes 30–60 seconds.

### Step 4 — Configure site

| Field | Value |
|-------|-------|
| **Site name** | DrupalMind Test (or anything you like) |
| **Site email address** | admin@drupalmind.local |
| **Username** | admin |
| **Password** | choose a strong password |
| **Default country** | your country |
| **Default time zone** | your timezone |

Uncheck **Receive email notifications** (Mailpit will catch them anyway).

Click **Save and continue**.

### Step 5 — Installation complete

Drupal will redirect you to the finished site at http://localhost:5500. You are now logged in as admin.

---

## 6. Automated Module Setup

This script installs Composer, Drush, all required modules, creates the API user, and configures SMTP — all in one go.

### Windows (PowerShell)

```powershell
docker cp scripts/setup-drupal.sh drupal:/tmp/setup-drupal.sh
docker exec -it drupal bash /tmp/setup-drupal.sh
```

### macOS / Linux

```bash
docker cp scripts/setup-drupal.sh drupal:/tmp/setup-drupal.sh
docker exec -it drupal bash /tmp/setup-drupal.sh
```

### What the script does

The script runs inside the container and performs these steps automatically:

| Step | Action |
|------|--------|
| 1 | Installs Composer at `/usr/local/bin/composer` |
| 2 | Installs Drush via Composer, symlinks to `/usr/local/bin/drush` |
| 3 | Installs modules: admin_toolbar, restui, jsonapi_extras, token, pathauto, metatag, smtp |
| 4 | Enables: jsonapi, rest, basic_auth, serialization + all installed modules |
| 5 | Sets JSON:API to read-only off (write access on) |
| 6 | Creates `api_agent` role with content CRUD permissions |
| 7 | Creates `apiuser` account with password `apiuser`, assigns `api_agent` role |
| 8 | Configures SMTP to point at Mailpit (host: `mailpit`, port: `1025`) |
| 9 | Clears all caches |

> **Estimated time:** 3–8 minutes depending on internet speed (Composer downloads packages).

Watch for any red `[FAIL]` lines. Warnings in yellow are usually safe to ignore.

---

## 7. Enable JSON:API Write Access

Even though the setup script enables write access via Drush, confirm it in the UI:

1. Go to: **http://localhost:5500/admin/config/services/jsonapi**
2. Under **Allowed operations** select:
   > ✅ Accept all JSON:API create, read, update, and delete operations
3. Click **Save configuration**

---

## 8. Verify the API

Test that the JSON:API is fully operational before starting the agents.

### Windows PowerShell

```powershell
# Test 1 — Public API discovery (no auth)
curl.exe http://localhost:5500/jsonapi

# Test 2 — Authenticated read
curl.exe -u apiuser:apiuser http://localhost:5500/jsonapi/node/article

# Test 3 — Create a test article (write access)
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
$json = '{"data":{"type":"node--article","attributes":{"title":"API Test Article","body":{"value":"Created by DrupalMind setup test.","format":"basic_html"}}}}'
[System.IO.File]::WriteAllText("$PWD\test.json", $json, $utf8NoBom)
curl.exe -u apiuser:apiuser -X POST -H "Content-Type: application/vnd.api+json" --data-binary "@test.json" http://localhost:5500/jsonapi/node/article
```

### macOS / Linux

```bash
# Test 1 — Public API discovery
curl http://localhost:5500/jsonapi | python3 -m json.tool

# Test 2 — Authenticated read
curl -u apiuser:apiuser http://localhost:5500/jsonapi/node/article

# Test 3 — Create a test article
curl -u apiuser:apiuser \
  -X POST \
  -H "Content-Type: application/vnd.api+json" \
  -d '{"data":{"type":"node--article","attributes":{"title":"API Test","body":{"value":"Hello from DrupalMind!","format":"basic_html"}}}}' \
  http://localhost:5500/jsonapi/node/article
```

### Expected responses

**Test 1** — Should return a JSON object listing all available API resource types.

**Test 2** — Should return `{"data": []}` (empty array — no articles yet).

**Test 3** — Should return HTTP 201 with the created article's full JSON including a UUID. Visit **http://localhost:5500** and your test article should appear on the front page.

---

## 9. Start the Agent System

Once Drupal is verified, add your API key to `.env` (if not done in Step 3) and start the agent containers:

```powershell
# Build and start agent containers
docker compose up -d drupalmind-agents drupalmind-ui
```

First run builds the Python and Node images — allow 3–5 minutes.

Check agent health:

```powershell
docker compose ps
curl.exe http://localhost:5511/health
```

Expected response from `/health`:
```json
{"status": "ok", "agents": "ready"}
```

---

## 10. Open the DrupalMind UI

Open your browser and go to: **http://localhost:5510**

The DrupalMind control panel will open. You will see:

- **Left panel** — URL/description input + agent status board
- **Centre** — Live agent log + build plan task board
- **Right panel** — Side-by-side source vs. built preview

To start your first migration:
1. Paste a website URL into the input field (or switch to **Describe** mode and type what you want)
2. Select **Full site migration**
3. Click **Start Build**
4. Watch the agents work in the live log

---

## 11. Service Reference

| Service | URL | Credentials |
|---------|-----|-------------|
| **Drupal site** | http://localhost:5500 | — |
| **Drupal admin** | http://localhost:5500/user/login | admin / *your password* |
| **JSON:API** | http://localhost:5500/jsonapi | apiuser / apiuser |
| **phpMyAdmin** | http://localhost:5501 | drupal / drupalpass123 |
| **Mailpit** (email) | http://localhost:5502 | — |
| **DrupalMind UI** | http://localhost:5510 | — |
| **Agent API** | http://localhost:5511 | — |
| **Redis** | localhost:5520 | — |

### Docker management commands

```powershell
# View running containers
docker compose ps

# View logs for a specific service
docker compose logs -f drupal
docker compose logs -f drupalmind-agents

# Restart a single service
docker compose restart drupal

# Stop all (keeps data)
docker compose stop

# Start all again
docker compose up -d

# Open a shell in any container
docker exec -it drupal bash
docker exec -it drupalmind_agents bash
```

### Useful Drush commands (run inside drupal container)

```bash
docker exec -it drupal bash
cd /opt/drupal

drush status                          # Drupal status overview
drush cr                              # Clear all caches
drush en MODULE_NAME -y               # Enable a module
drush pmu MODULE_NAME -y              # Disable a module
drush user:list                       # List all users
drush role:list                       # List all roles
drush config:export                   # Export configuration
drush config:import                   # Import configuration
drush updatedb                        # Run pending DB updates
```

---

## 12. Troubleshooting

### `drupal_db` container stays unhealthy

This means MySQL hasn't started yet or the credentials are wrong.

```powershell
# Check MySQL logs
docker logs drupal_db

# If you see auth errors, hard reset the DB volume
docker compose down
docker volume rm drupal-mind_db_data
docker compose up -d
```

### Drupal shows a white screen or 500 error

```powershell
# Check Drupal PHP errors
docker logs drupal

# Or access error log inside container
docker exec -it drupal bash -c "tail -50 /var/log/apache2/error.log"
```

### `curl.exe` not found on Windows

`curl.exe` ships with Windows 10 build 1803+ and Windows 11. If missing:

```powershell
winget install curl.se.curl
```

Or use PowerShell's native equivalent:

```powershell
Invoke-WebRequest -Uri "http://localhost:5500/jsonapi" -UseBasicParsing
```

### Composer runs out of memory

```bash
docker exec -it drupal bash
cd /opt/drupal
php -d memory_limit=-1 /usr/local/bin/composer install
```

### Ports 5500–5520 already in use

Edit `docker-compose.yml` and change the left side of the port mapping:

```yaml
ports:
  - "6500:80"   # was 5500:80 — change left number only
```

Then run `docker compose up -d` again.

### JSON:API returns 405 Method Not Allowed on POST

Write access is disabled. Go to:
http://localhost:5500/admin/config/services/jsonapi
and enable **Accept all JSON:API operations**.

### Agent container fails to start

Check your `.env` file has a valid `ANTHROPIC_API_KEY`:

```powershell
docker logs drupalmind_agents
```

If you see `AuthenticationError`, the API key is missing or invalid.

---

## 13. Resetting Everything

### Soft reset — keep Drupal data, restart containers

```powershell
docker compose down
docker compose up -d
```

### Hard reset — wipe database and Drupal files, start fresh

```powershell
docker compose down -v
docker compose up -d
# Then re-run the Drupal installer at http://localhost:5500
```

### Reset only the database

```powershell
docker compose stop db
docker volume rm drupal-mind_db_data
docker compose up -d db
# Then re-run the Drupal installer
```

### Update to latest images

```powershell
docker compose pull
docker compose up -d
```

---

*DrupalMind — Agentic AI Website Builder*  
*Documentation version 0.1*
