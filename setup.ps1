# ─────────────────────────────────────────────────────────────
# DrupalMind — Windows PowerShell Setup Script
# Run from the repo root: .\scripts\setup.ps1
# ─────────────────────────────────────────────────────────────

param(
    [switch]$SkipDockerCheck,
    [switch]$SkipDrupalInstall
)

$ErrorActionPreference = "Stop"

function Write-Step  { param($msg) Write-Host "`n[STEP] $msg" -ForegroundColor Cyan }
function Write-OK    { param($msg) Write-Host "  [OK] $msg"   -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "  [!!] $msg"   -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host " [ERR] $msg"   -ForegroundColor Red; exit 1 }

Write-Host @"

  ____                  _       _ __  __ _           _ 
 |  _ \ _ __ _   _ _ __| | __ _| |  \/  (_)_ __   __| |
 | | | | '__| | | | '_ \ |/ _  | | |\/| | | '_ \ / _  |
 | |_| | |  | |_| | |_) | | (_| | | |  | | | | | | (_| |
 |____/|_|   \__,_| .__/|_|\__,_|_|_|  |_|_|_| |_|\__,_|
                  |_|  Agentic Drupal Builder — Setup

"@ -ForegroundColor Magenta

# ── 1. Check Docker ───────────────────────────────────────────
Write-Step "Checking Docker..."
if (-not $SkipDockerCheck) {
    try {
        $dockerVersion = docker --version 2>&1
        Write-OK "Docker found: $dockerVersion"
    } catch {
        Write-Fail "Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    }

    try {
        $composeVersion = docker compose version 2>&1
        Write-OK "Docker Compose found: $composeVersion"
    } catch {
        Write-Fail "Docker Compose not found. Update Docker Desktop to a recent version."
    }
}

# ── 2. Create .env from example ───────────────────────────────
Write-Step "Setting up environment file..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Warn ".env created from .env.example"
    Write-Warn "IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY before starting agents!"
} else {
    Write-OK ".env already exists"
}

# ── 3. Start Docker stack ─────────────────────────────────────
Write-Step "Starting Docker containers..."
docker compose up -d drupal db phpmyadmin mailpit redis

Write-OK "Containers starting..."
Write-Host "  Waiting 30s for MySQL to become healthy..." -ForegroundColor Gray
Start-Sleep -Seconds 30

# Wait for MySQL health
$retries = 0
while ($retries -lt 10) {
    $health = docker inspect --format='{{.State.Health.Status}}' drupal_db 2>&1
    if ($health -eq "healthy") {
        Write-OK "MySQL is healthy"
        break
    }
    Write-Host "  Still waiting for MySQL... ($health)" -ForegroundColor Gray
    Start-Sleep -Seconds 10
    $retries++
}

# ── 4. Drupal web installer ───────────────────────────────────
if (-not $SkipDrupalInstall) {
    Write-Step "Drupal Web Installer"
    Write-Host @"

  ┌─────────────────────────────────────────────────────┐
  │  Open http://localhost:5500 in your browser         │
  │  and complete the Drupal installer with:            │
  │                                                     │
  │  Profile:   Standard                                │
  │  DB type:   MySQL                                   │
  │  DB name:   drupal                                  │
  │  DB user:   drupal                                  │
  │  DB pass:   drupalpass123                           │
  │  DB host:   db          (under Advanced Options)    │
  │  DB port:   3306        (under Advanced Options)    │
  │                                                     │
  │  Press ENTER here once the installer is complete.   │
  └─────────────────────────────────────────────────────┘
"@ -ForegroundColor Cyan

    Read-Host "  Press ENTER when Drupal installer is complete"
}

# ── 5. Run Drupal module setup ────────────────────────────────
Write-Step "Installing Drupal modules and configuring API..."

# Copy setup script into container and run it
docker cp scripts/setup-drupal.sh drupal:/tmp/setup-drupal.sh
docker exec drupal bash /tmp/setup-drupal.sh

Write-OK "Drupal configured successfully"

# ── 6. Enable JSON:API write access ──────────────────────────
Write-Step "Final configuration check..."
Write-Host @"

  ┌─────────────────────────────────────────────────────┐
  │  Enable JSON:API write access in Drupal:            │
  │                                                     │
  │  1. Go to: http://localhost:5500/admin/config/      │
  │            services/jsonapi                         │
  │  2. Select: "Accept all JSON:API operations"        │
  │  3. Click Save                                      │
  │                                                     │
  │  Press ENTER when done.                             │
  └─────────────────────────────────────────────────────┘
"@ -ForegroundColor Yellow

Read-Host "  Press ENTER when JSON:API write access is enabled"

# ── 7. Test the API ───────────────────────────────────────────
Write-Step "Testing API connection..."
try {
    $response = curl.exe -s -o NUL -w "%{http_code}" -u apiuser:apiuser http://localhost:5500/jsonapi/node/article
    if ($response -eq "200") {
        Write-OK "JSON:API responding correctly (HTTP 200)"
    } else {
        Write-Warn "API returned HTTP $response — check Drupal configuration"
    }
} catch {
    Write-Warn "Could not test API automatically. Check manually at http://localhost:5500/jsonapi"
}

# ── 8. Summary ────────────────────────────────────────────────
Write-Host @"

  ════════════════════════════════════════════════════════
   DrupalMind Setup Complete!
  ════════════════════════════════════════════════════════

   Services:
    Drupal         http://localhost:5500
    Admin Panel    http://localhost:5500/user/login
    JSON:API       http://localhost:5500/jsonapi
    phpMyAdmin     http://localhost:5501
    Mailpit        http://localhost:5502
    Redis          localhost:5520

   Credentials:
    Drupal API     apiuser / apiuser
    DB user        drupal / drupalpass123
    DB root        root / rootsecret123

   Next Steps:
    1. Edit .env and add your ANTHROPIC_API_KEY
    2. Run: docker compose up -d  (starts agent system)
    3. Open: http://localhost:5510  (DrupalMind UI)

  ════════════════════════════════════════════════════════

"@ -ForegroundColor Green
