# Environment Setup Guide

This document explains how to configure environment variables for CodeProvenance.

## Overview

We maintain two environment files, both in `src/backend/`:

| File                          | Purpose                          | Safe to Commit? | When to Use |
|-------------------------------|----------------------------------|------------------|-------------|
| `.env.example`                | Development template             | Yes             | Reference for new setups |
| `.env.local`                  | Your actual secrets              | **No**          | Local development and deployed hosts |

Production does not use a template file checked into the repo: `deploy/setup.sh`
generates `src/backend/.env.local` on the server from `deploy/deploy.conf`, with fresh
random `AUTH_JWT_SECRET` / `WEBHOOK_SECRET_KEY` values. See `deploy/README.md`.

**Never commit** `.env.local` or any file containing real secrets.

## Local Development Setup

1. Copy the development template:
   ```bash
   cp src/backend/.env.example src/backend/.env.local
   ```

2. Edit `src/backend/.env.local` and fill in the required values:
   - `DATABASE_URL` (your local or remote database)
   - `AUTH_JWT_SECRET` (generate a strong random string)

3. That is the whole setup — `src/backend/.env.local` is the **only** env file this
   project uses. Do **not** create a `.env.local` at the repo root or in `src/`
   (see [Common Pitfalls](#common-pitfalls) for why they silently do nothing).

## Production Setup

1. Run `sudo bash deploy/setup.sh`. It writes `src/backend/.env.local` on the server
   (derived from `deploy/deploy.conf`) with `APP_ENV=production`, `DEBUG=false`,
   `AUTH_COOKIE_SECURE=true` and freshly generated random secrets. Do not hand-edit the
   generated file — see `deploy/README.md`.

2. **Strongly recommended**: inject secrets at runtime with your platform's secret
   manager instead of relying on a file on disk:
   - Doppler
   - AWS Secrets Manager
   - HashiCorp Vault
   - Vercel / Railway / Render environment variables

3. Never commit the generated `.env.local` (it is already git-ignored).

4. To rotate an aged or exposed secret, see
   [If a Secret Was Committed](#if-a-secret-was-committed) and the rotation procedure in
   `deploy/README.md`.

## Security Best Practices

- Rotate `AUTH_JWT_SECRET` periodically (especially after any suspected exposure).
- Never reuse the same JWT secret between development and production.
- Keep `DATABASE_URL` credentials separate per environment.
- Prefer managed Redis and databases over localhost connections in production.
- Use absolute paths for `UPLOAD_DIR` in production (or object storage like S3/R2).

## Common Pitfalls

- **A second `.env.local` at the repo root.** Nothing reads it. Every backend loader resolves `.env.local` relative to `src/backend/` (`config/settings.py`, `config/database.py`, `api/server.py`, `integrations/ai_detection.py`, `alembic/env.py`, `scripts/*.py`, `scripts/start.sh`), and Next.js only reads env files from its own project directory (`src/frontend/`, the folder holding `next.config.ts`) — never the repo root. A root file is silently ignored, so it only creates confusion plus a second copy of your secrets.
- **Creating `src/frontend/.env.local` for the dashboard's backend URL.** The supported path is the `API_URL` / `NEXT_PUBLIC_API_URL` export already performed by `scripts/start.sh` (and by `deploy/setup.sh`, `deploy/update.sh`).
- Forgetting to update `CORS_ALLOWED_ORIGINS` when changing domains.
- Using the same `.env.local` values in production.
- Committing real secrets (even temporarily) — deleting the file in a later commit does **not** remove it from git history. See [If a Secret Was Committed](#if-a-secret-was-committed).

## Quick Reference

- Backend loads environment from: `src/backend/.env.local` — the only env file that holds secrets.
- Frontend needs **no** env file: `scripts/start.sh` and the `deploy/` scripts export `API_URL` / `NEXT_PUBLIC_API_URL` before Next.js starts.
- Starting the dashboard on its own (`cd src/frontend && npm run dev`) requires the backend URL inline, because `next.config.ts` refuses to start without it: `API_URL=http://127.0.0.1:8000 npm run dev`
- Always run `source /home/tsun/Documents/CodeProvenance/venv/bin/activate` before working with Python.

## If a Secret Was Committed

Deleting a file in a later commit does **not** remove it from git history, and by the
time you notice, a public repository has likely already been cloned or crawled.
**Rotate the credential first** — purging history afterwards is only cosmetic.

1. Rotate the exposed value at its source. For `DATABASE_URL`, reset the password of
   that database role (Neon: console → project → Roles → Reset password). For
   `AUTH_JWT_SECRET` or `WEBHOOK_SECRET_KEY`, generate a fresh value with
   `openssl rand -hex 32`.
2. Update `src/backend/.env.local` with the new value and restart the services
   (`scripts/start.sh`, or the `integritydesk-*` systemd units in production).
3. Audit history for the old value: `git log --all -S '<old-secret-value>' --oneline`.
   `deploy/README.md` documents the same procedure for production secrets.
4. (Optional) Purge history with `git filter-repo`/BFG and force-push. Only worth it on
   a private repo you control, and it needs coordinating with every existing clone;
   rotation is what actually closes the exposure.

Note: the `secret-scan` (gitleaks) job in `.github/workflows/ci.yml` scans only the
pushed commit range, so a credential committed long ago and deleted since will not be
flagged by CI.

If you are using Codex or other AI agents for long sessions:

- Always start by reading these three files in order:
  1. `docs/CURRENT_FOCUS.md`
  2. `docs/SCHEMA_OVERVIEW.md`
  3. `docs/BENCHMARK_WORK.md`

- Prefer these small, high-signal files over large source files (especially `src/backend/models/database.py`).
