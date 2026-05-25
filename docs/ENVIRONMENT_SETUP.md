# Environment Setup Guide

This document explains how to configure environment variables for CodeProvenance.

## Overview

We maintain three environment files in `src/backend/`:

| File                          | Purpose                          | Safe to Commit? | When to Use |
|-------------------------------|----------------------------------|------------------|-------------|
| `.env.example`                | Development template             | Yes             | Local development |
| `.env.production.example`     | Production template              | Yes             | Deployment / CI |
| `.env.local`                  | Your actual local secrets        | **No**          | Local development only |

**Never commit** `.env.local` or any file containing real secrets.

## Local Development Setup

1. Copy the development template:
   ```bash
   cp src/backend/.env.example src/backend/.env.local
   ```

2. Edit `src/backend/.env.local` and fill in the required values:
   - `DATABASE_URL` (your local or remote database)
   - `AUTH_JWT_SECRET` (generate a strong random string)

3. (Optional) The root `.env.local` and `src/.env.local` have been cleaned up. Do **not** create new ones in those locations.

## Production Setup

1. Copy the production template:
   ```bash
   cp src/backend/.env.production.example src/backend/.env.production
   ```

2. Replace all placeholders with real values.

3. **Strongly recommended**:
   - Do **not** commit `.env.production`
   - Inject secrets at runtime using your platform’s secret manager:
     - Doppler
     - AWS Secrets Manager
     - HashiCorp Vault
     - Vercel / Railway / Render environment variables

4. Set `APP_ENV=production` and `DEBUG=false`.

## Security Best Practices

- Rotate `AUTH_JWT_SECRET` periodically (especially after any suspected exposure).
- Never reuse the same JWT secret between development and production.
- Keep `DATABASE_URL` credentials separate per environment.
- Prefer managed Redis and databases over localhost connections in production.
- Use absolute paths for `UPLOAD_DIR` in production (or object storage like S3/R2).

## Common Pitfalls

- Having multiple `.env.local` files in `src/`, `src/frontend/`, or the project root (we have cleaned these up).
- Forgetting to update `CORS_ALLOWED_ORIGINS` when changing domains.
- Using the same `.env.local` values in production.
- Committing real secrets (even temporarily).

## Quick Reference

- Backend loads environment from: `src/backend/.env.local`
- Frontend loads from: `src/frontend/.env.local` (standard Next.js behavior)
- Always run `source /home/tsun/Documents/CodeProvenance/venv/bin/activate` before working with Python.

If you are using Codex or other AI agents for long sessions:

- Always start by reading these three files in order:
  1. `docs/CURRENT_FOCUS.md`
  2. `docs/SCHEMA_OVERVIEW.md`
  3. `docs/BENCHMARK_WORK.md`

- Prefer these small, high-signal files over large source files (especially `src/backend/models/database.py`).
