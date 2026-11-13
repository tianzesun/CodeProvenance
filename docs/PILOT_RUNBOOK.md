# Pilot runbook

One checklist for taking IntegrityDesk to a pilot with real courses. Work through it in order; each
section links to the detailed doc. Tick boxes in a copy for your pilot, not in this file.

## 1. Approvals (before any real student data)

- [ ] **Information Risk Assessment** completed (uoft.me/Information-Risk-Assessment). It should
      cover: student submissions stored in the database (Neon), who can see them (owners, sharing,
      organization membership: docs/ORGANIZATION_MEMBERSHIP_DESIGN.md), retention, and any
      third-party service enabled in §3.
- [ ] **Data steward / Privacy Office** sign-off on what is collected and the labelled-data request
      (docs/STUDENT_DATA_REQUEST_PACK.md).
- [ ] **Pilot scope agreed:** which courses, which instructors, start and end dates, and who the
      administrator is.
- [ ] **Instructors briefed** (§8).

## 2. Freeze deployments for the pilot

`deploy/auto-update.sh` (when its timer is enabled) deploys every commit on `main` within about two
minutes and **never runs migrations**. During the pilot, deploy deliberately instead:

```bash
sudo systemctl disable --now integritydesk-auto-update.timer   # if enabled
systemctl list-timers | grep integritydesk                     # should list nothing
```

Every change then goes: merge → staging (§5, §6) → production (§5).

## 3. Configuration

Set these in the backend environment (the same place as `DATABASE_URL`). Secrets come from the
managed secret store, never the repository.

| Setting | Pilot value | Why |
|---|---|---|
| `AUTH_JWT_SECRET`, `SETTINGS_ENCRYPTION_KEY` | from the secret store | sessions and saved credentials |
| `AUTH_COOKIE_SECURE` | `true` | production checks require it |
| `INSTITUTION_NAME` | e.g. `University of Toronto` | the organization's name (#44, #45) |
| `INSTITUTION_EMAIL_DOMAINS` | e.g. `utoronto.ca` | who joins automatically; others wait for an admin |
| `GUEST_LOGIN_ENABLED` | `false` (recommended) | no anonymous use during a pilot with real data |
| `AUTH_SESSION_MAX_HOURS` | `168` (default) | longest a sign-in lasts (#48) |

In the app's **Settings**, per workspace:
- [ ] **AI authorship checks: Off** (the default since #41). The detector ranks near chance on
      unfamiliar code (docs/AI_DETECTOR_VS_TURNITIN.md); turn it on only if the IRA and the
      instructors accept that.
- [ ] **External source scanning and AI providers** off, unless the IRA covers sending student code
      to those services.

## 4. Before the first deploy

- [ ] CI is green on the exact commit you will deploy.
- [ ] **Backup** the database: a Neon branch or point-in-time restore point, or `pg_dump`.
- [ ] The Analysis worker and Redis are running (`sudo bash deploy/status.sh`). Uploads queue for
      the worker; without one they wait forever.

## 5. Deploy, and roll back

```bash
# on the server, as the deploy user
git fetch && git checkout <commit>            # the commit CI passed
sudo bash deploy/update.sh                    # deps, frontend build, restart (no migrations)

# membership (only the first time): dry run, read it, then migrate
python scripts/institution_membership_dry_run.py          # add --list to see who joins
alembic upgrade head
python scripts/institution_membership_dry_run.py          # should show nobody left to join
python scripts/check_schema_drift.py                      # should report nothing missing
sudo bash deploy/status.sh
```

Tell users before this deploy: **everyone signs in again once** (#48 stops renewing older sessions).

**Rollback:** `alembic downgrade <previous head>` (the membership migration's downgrade restores the
exact previous memberships), `git checkout <previous commit>`, `sudo bash deploy/update.sh`. If data
went wrong, restore the backup from §4.

## 6. Smoke tests (staging, then once on production)

Use two instructor accounts on a listed domain (A, B) and one outside it (C).

| Check | Expected |
|---|---|
| A uploads a small class (a ZIP of 10+ files) | Progress, then a results page with ranked pairs |
| A opens a flagged pair | Evidence Signals lists what raised the score (chunk hash match first, usually) |
| A opens a case from that pair | Case created, linked to the pair |
| A shares the course with B | B sees the course, its analysis and case; C does not |
| B opens A's unshared analysis by its link | "not found" |
| C tries to open a case | 403 asking an admin to add them; admin adds C, then it works |
| A opens the dossier and its PDF | Students banded; coverage shows AI detection as not checked |
| A downloads the Integrity Assessment Report (PDF) | "Whole class", block types, no CI or sanctions table; **check the layout by eye** |
| A resets their password ("Forgot password", emailed link) | Their other signed-in browser is signed out |

## 7. Go / no-go

- [ ] All smoke tests pass.
- [ ] **Load test** at the largest pilot class: `locust -f src/backend/load_tests/locustfile.py
      --host https://<staging-host>` (docs/LOAD_TESTING.md), with the analysis worker running.
- [ ] **Restore test:** restore the §4 backup into a scratch database and open one analysis from it.
- [ ] Approvals in §1 complete.

## 8. What to tell instructors

- A score ranks pairs for review; it is **not proof**. Read the matched code and the evidence before
  acting, and follow your institution's academic integrity process.
- It catches near-verbatim and renamed copies well; copies rewritten inside a student's own code are
  often missed (as with JPlag and Dolos). Short files and shared starter code are held at review.
- AI authorship checks are off.
- Work is private until you share it. If you cannot share or open cases, ask the administrator to
  add you to the organization.
- You will be asked to sign in again once after the pilot deploy, and at least weekly after that.

## 9. During the pilot

- Keep deployments frozen except fixes, each through staging (§2, §5, §6).
- Collect instructor feedback on false flags and missed copies; this is the labelled data the bands
  wait for (docs/STUDENT_DATA_REQUEST_PACK.md, `class_evaluation_runner --student-holdout`).
- **Suspected privacy or security incident** (wrong person seeing student work, a leaked
  credential): stop and report to privacy.utoronto.ca or security.utoronto.ca before changing
  anything.
