#!/usr/bin/env bash
# =============================================================================
# IntegrityDesk - System Bootstrap
# Installs OS-level packages required to run the app (Python, Node, nginx,
# certbot, Redis, build tools, PDF rendering libs). Run once per server.
#
#   sudo bash deploy/bootstrap.sh
#
# Safe to re-run (idempotent).
# =============================================================================

set -euo pipefail

log() { echo -e "\033[1;32m[bootstrap]\033[0m $*"; }
die() { echo -e "\033[1;31m[bootstrap ERROR]\033[0m $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash deploy/bootstrap.sh"

export DEBIAN_FRONTEND=noninteractive

log "Updating apt package lists..."
apt-get update -y

log "Installing base packages..."
apt-get install -y --no-install-recommends \
    curl wget git ca-certificates gnupg lsb-release \
    python3 python3-venv python3-pip python3-dev \
    build-essential gcc g++ make \
    libffi-dev libjpeg-dev libopenjp2-7 \
    libcairo2 libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    apache2 apache2-utils certbot python3-certbot-apache \
    redis-server \
    lsof \
    || die "Base package install failed"

# --- Node.js 22 LTS (required for Next.js 16 / React 19) ----------------------
if ! command -v node >/dev/null 2>&1 || [ "$(node -r semver -e 'process.exit(require("semver").major(process.version) < 20 ? 1 : 0)' 2>/dev/null || echo 0)" = "1" ]; then
    log "Installing Node.js 22 LTS via NodeSource..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs || die "Node.js install failed"
fi

log "Verifying versions..."
python3 --version
node --version
npm --version

log "Enabling and starting redis-server..."
systemctl enable redis-server
systemctl start redis-server

log "Enabling Apache proxy modules..."
a2enmod proxy proxy_http proxy_wstunnel rewrite headers ssl >/dev/null 2>&1 || true

log ""
log "Bootstrap complete. Next step:"
log "  cp deploy/deploy.conf.example deploy.conf   # edit with your values"
log "  sudo bash deploy/setup.sh"
