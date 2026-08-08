# IntegrityDesk Deployment Guide

This directory contains everything needed to deploy IntegrityDesk to a fresh
Ubuntu/Debian server behind **Apache** (or nginx) with TLS (Let's Encrypt),
managed by systemd.

## Architecture

| Service | Port | Unit |
|---|---|---|
| FastAPI backend | 127.0.0.1:8000 | `integritydesk-backend` |
| Next.js dashboard | 127.0.0.1:3000 | `integritydesk-dashboard` |
| Webhook worker (needs Redis) | - | `integritydesk-worker` |
| Embedding server *(optional)* | 127.0.0.1:8001 | `integritydesk-embedding` |

The web server (Apache by default) listens on 443 and routes `/api`, `/report`,
and `/docs` to the backend, everything else to the dashboard.

## Requirements

- Ubuntu 20.04/22.04/24.04 or Debian 11/12
- A managed PostgreSQL database (Neon/RDS etc.) — SQLite is **not** supported
- A domain name pointed at the server
- Root/sudo access
- Optional: a Python virtualenv at `$APP_DIR/venv` (set `SKIP_VENV=1` if you
  already have one)

## First-time install

```bash
# 1. Clone the repo onto the server
git clone https://github.com/tianzesun/CodeProvenance.git /home/tsun/projects/CodeProvenance
cd /home/tsun/projects/CodeProvenance

# 2. Install OS packages (python, node 22, apache, certbot, redis, build tools)
sudo bash deploy/bootstrap.sh

# 3. Create and edit your config
cp deploy/deploy.conf.example deploy.conf
vim deploy.conf   # set APP_DOMAIN, CERTBOT_EMAIL, DATABASE_URL, APP_DIR, ...

# 4. Build and start everything
sudo bash deploy/setup.sh
```

That's it. After the script finishes, the dashboard is live at
`https://your-domain`.

## After every `git pull`

```bash
sudo bash deploy/update.sh
```

This reinstalls Python deps (if changed), rebuilds the frontend, and restarts
the services. It does **not** touch `deploy.conf` or the generated
`.env.local`.

## Day-to-day operations

```bash
sudo bash deploy/status.sh    # health of all services
sudo bash deploy/restart.sh   # restart all services

systemctl status integritydesk-backend
journalctl -u integritydesk-backend -f    # tail backend logs
journalctl -u integritydesk-dashboard -f  # tail dashboard logs
```

## Configuration reference (`deploy.conf`)

| Key | Description |
|---|---|
| `WEB_SERVER` | `apache` (default) or `nginx` |
| `APP_DOMAIN` | Public domain (no scheme) |
| `CERTBOT_EMAIL` | Email for cert expiry notices |
| `DATABASE_URL` | PostgreSQL connection string (required) |
| `REDIS_URL` | Redis URL for the webhook worker |
| `RUN_USER` | System user that runs services (created if missing) |
| `APP_DIR` | Absolute path to the repo (e.g. `/home/tsun/projects/CodeProvenance`) |
| `SKIP_VENV` | `1` to reuse an existing venv at `$APP_DIR/venv` (skips creation) |
| `OPENAI_API_KEY` | Optional; enables OpenAI embeddings |
| `EMBEDDING_SERVER_URL` | Set to enable the local embedding server |

## Notes

- **Web server**: both `deploy/apache/integritydesk.conf` and
  `deploy/nginx/integritydesk.conf` templates are included. `setup.sh` picks
  one based on `WEB_SERVER`. Certbot is invoked with the matching plugin
  (`certbot --apache` / `certbot --nginx`).
- **Venv**: with `SKIP_VENV=1`, setup skips `python3 -m venv` and only runs
  `pip install -r requirements.txt` into the existing venv.
- **Lean by default**: the deployment does not install torch /
  sentence-transformers. The embedding engine falls back to OpenAI or is
  skipped. To enable local embeddings later, `pip install -r requirements-gpu.txt`
  plus `sentence-transformers`, set `EMBEDDING_SERVER_URL`, and re-run
  `sudo bash deploy/setup.sh`.
- **Webhook worker**: requires `REDIS_URL` to be reachable. If you don't need
  webhooks, you can `systemctl disable integritydesk-worker`.
- **Secrets**: `deploy.conf` and `src/backend/.env.local` are git-ignored and
  generated on the server. Never commit them.
- The `.env.local` is generated with a random `AUTH_JWT_SECRET` and
  `WEBHOOK_SECRET_KEY` on each setup run.
