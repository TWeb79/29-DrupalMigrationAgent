#!/bin/bash
# ─────────────────────────────────────────────────────────────
# DrupalMind — Drupal Setup Script
# Run this INSIDE the drupal container after the web installer
# Usage: docker exec -it drupal bash /tmp/setup-drupal.sh
# ─────────────────────────────────────────────────────────────

set -e

DRUPAL_ROOT="/opt/drupal"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[SETUP]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
fail() { echo -e "${RED}[FAIL]${NC}  $1"; exit 1; }

log "Starting DrupalMind setup..."
cd $DRUPAL_ROOT

# ── 1. Install Composer globally if missing ───────────────────
if ! command -v composer &>/dev/null; then
  log "Installing Composer..."
  curl -sS https://getcomposer.org/installer | php
  mv composer.phar /usr/local/bin/composer
  chmod +x /usr/local/bin/composer
else
  log "Composer already installed: $(composer --version)"
fi

# ── 2. Install Drush if missing ───────────────────────────────
if [ ! -f "$DRUPAL_ROOT/vendor/bin/drush" ]; then
  log "Installing Drush via Composer..."
  composer require drush/drush --no-interaction
else
  log "Drush already installed."
fi

# Symlink drush globally
if [ ! -f "/usr/local/bin/drush" ]; then
  ln -s $DRUPAL_ROOT/vendor/bin/drush /usr/local/bin/drush
  log "Drush symlinked to /usr/local/bin/drush"
fi

# ── 3. Install required Drupal modules ───────────────────────
log "Installing Drupal modules via Composer..."
composer require \
  drupal/admin_toolbar \
  drupal/restui \
  drupal/jsonapi_extras \
  drupal/token \
  drupal/pathauto \
  drupal/metatag \
  drupal/smtp \
  --no-interaction

# ── 4. Enable modules ─────────────────────────────────────────
log "Enabling modules..."
drush en \
  jsonapi \
  rest \
  restui \
  basic_auth \
  serialization \
  admin_toolbar \
  admin_toolbar_tools \
  jsonapi_extras \
  token \
  pathauto \
  metatag \
  -y

# ── 5. Enable JSON:API write access ──────────────────────────
log "Enabling JSON:API write operations..."
drush config:set jsonapi.settings read_only 0 -y

# ── 6. Create API user ────────────────────────────────────────
log "Creating API user role..."
drush role:create "api_agent" "API Agent" 2>/dev/null || warn "Role may already exist"

log "Granting API Agent permissions..."
drush role:perm:add api_agent \
  "access content" \
  "create article content" \
  "edit any article content" \
  "delete any article content" \
  "create page content" \
  "edit any page content" \
  "delete any page content" \
  "access GET on Content resource" \
  "access PATCH on Content resource" \
  "access POST on Content resource" \
  "access DELETE on Content resource" \
  "restful get entity:node" \
  "restful post entity:node" \
  "restful patch entity:node" \
  "restful delete entity:node" \
  2>/dev/null || warn "Some permissions may not exist yet — assign manually if needed"

log "Creating apiuser account..."
drush user:create apiuser --mail="api@drupalmind.local" --password="apiuser" 2>/dev/null || warn "User may already exist"
drush user:role:add api_agent apiuser

# ── 7. Configure SMTP to use Mailpit ─────────────────────────
log "Configuring SMTP to use Mailpit..."
drush en smtp -y 2>/dev/null || true
drush config:set smtp.settings smtp_on 1 -y 2>/dev/null || true
drush config:set smtp.settings smtp_host mailpit -y 2>/dev/null || true
drush config:set smtp.settings smtp_port 1025 -y 2>/dev/null || true
drush config:set smtp.settings smtp_protocol standard -y 2>/dev/null || true

# ── 8. Clear all caches ───────────────────────────────────────
log "Clearing caches..."
drush cr

# ── 9. Final status ───────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  DrupalMind Drupal Setup Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Drupal:       http://localhost:5500"
echo "  Admin:        http://localhost:5500/user/login"
echo "  JSON:API:     http://localhost:5500/jsonapi"
echo "  phpMyAdmin:   http://localhost:5501"
echo "  Mailpit:      http://localhost:5502"
echo "  API User:     apiuser / apiuser"
echo ""
echo -e "${YELLOW}  Next: Set up JSON:API permissions at${NC}"
echo "  http://localhost:5500/admin/config/services/jsonapi"
echo ""
