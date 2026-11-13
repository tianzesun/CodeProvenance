# Design: organization membership (draft for review)

**Status:** decisions made (§ 8); step 1, the migration and dry run, is implemented. **Risk:** high: it changes existing users' data and what
each person can see. Nothing here should be built before the decisions in § 8 are made.

## 1. Problem

Sharing, course creation and the colleague list all depend on `users.organization_id`, but
nothing in the product ever sets it:

| How a user is created | Organization | Workspace (`tenant_id`) |
|---|---|---|
| Bootstrap admin (`server.py` `_bootstrap_admin_sync`) | none | new |
| Self-registration (`/api/auth/register`) | none | new |
| Admin creates a user (`POST /api/admin/users`) | none | new (`_create_tenant` always creates) |
| Bulk import (`/api/admin/users/import`) | none | one new workspace per import batch, if `default_tenant_name` is given |
| `scripts/seed_demo_data.py` (manual, not in the deploy docs) | "Demo University", **first user only** | unchanged |

Consequences, read from the code (not yet confirmed against a live database):

- **Sharing does not work.** The Share dialog lists colleagues from `/api/users`, which answers
  403 "User is not associated with an organization" (`routes/users.py`). Sharing with a named
  person is refused unless they are in the sharer's workspace (`sharing.set_sharing`), and
  "Everyone in your organization" falls back to the sharer's own workspace, which usually
  contains only the sharer (`sharing.workspace_id`).
- **Terms and courses cannot be created** by anyone without an organization:
  `POST /api/terms` and `POST /api/courses` answer 400 "No organization associated with user"
  (`routes/academic.py`).
- **Every admin is deployment-wide.** No admin can be bound to one organization, so the
  "workspace admin vs platform admin" distinction in `sharing.AccessScope` never applies.

It all fails closed (nothing leaks), but courses and sharing, both core to the review workflow,
do not work for accounts the product itself creates.

**First step before any code:** count reality in production.

```sql
SELECT count(*) FILTER (WHERE organization_id IS NULL) AS without_org,
       count(*) FILTER (WHERE organization_id IS NOT NULL) AS with_org
FROM users WHERE is_active;
SELECT id, name FROM organizations;
SELECT organization_id, count(*) FROM courses GROUP BY 1;
```

## 2. Goals and non-goals

Goals:
- Every member of the institution belongs to its organization, so sharing, the colleague list
  and course creation work as the rollout guide (`docs/ROLLOUT_SHARING_AND_SETTINGS.md`)
  describes.
- Membership is deliberate: nobody becomes a member just by being able to register.
- The migration is reversible and changes nothing it cannot undo.

Non-goals:
- Hosting several institutions on one server. The model below allows it later, but this change
  assumes **one organization per deployment**.
- Changing per-user workspace settings (`tenant_id`): each person keeps their own settings.

## 3. Proposed model

One organization per deployment, the **institution** (e.g. "University of Toronto"). A user is
either a member (`organization_id` set) or not (`NULL`). Membership is what grants:
the colleague list, sharing with colleagues or the whole organization, creating terms and
courses, and (for admins) reach over the organization's courses.

Admins stay deployment-wide for user management, as they are today. Scoping admins per
organization is only needed for multi-institution hosting (a non-goal).

## 4. Who becomes a member

| Path | Proposed |
|---|---|
| Bootstrap admin | Creates the organization (name from a new `INSTITUTION_NAME` setting, or the bootstrap form) and joins it. |
| Admin creates a user | Joins the creating admin's organization. |
| Bulk import | Each imported user joins the importing admin's organization. |
| Self-registration | **Decision 1** (§ 8). Recommended: not a member until an admin adds them; optionally auto-join when the email domain is in a new `INSTITUTION_EMAIL_DOMAINS` setting (e.g. `utoronto.ca`), and a `REGISTRATION_ENABLED` switch to turn self-registration off. |
| Admin page | A "Member" column, plus **Add to organization** / **Remove from organization** per user. Removing does not delete their work; it stops new sharing reaching them. |

Why not auto-join every registrant: registration is open to any verified email address, so
auto-joining would let anyone who registers see everything shared with "Everyone in your
organization".

## 5. Migration (Alembic, reversible)

`add_institution_membership`, data-only (no schema change beyond a bookkeeping table):

1. **Pick the organization.** None exists: create one named `INSTITUTION_NAME` (default
   "Institution"). Exactly one exists (e.g. the seeded "Demo University"): use it, renamed to
   `INSTITUTION_NAME` when that is set. More than one: **change nothing** and log why; mapping
   users to several organizations needs a human (multi-institution is a non-goal). It skips
   rather than fails, because a failing migration would block every deploy.
2. **Backfill members.** Set `organization_id` for active users with none, using the rule from
   **Decision 3**. Users who already have an organization are left alone.
3. **Record what changed** in `org_membership_backfill (user_id, created_org_id)`, one row per
   user changed, so the downgrade is exact.
4. **Courses and terms** already require an organization, so existing rows keep theirs. If
   step 1 created a new organization while seeded courses sit in "Demo University", the
   migration stops and asks for the mapping rather than guessing.

Downgrade: set `organization_id = NULL` for exactly the recorded users, delete the organization
only if the migration created it and nothing else references it, drop the bookkeeping table.

Before production: back up the database; run a dry-run script that prints the counts above and
who would join; apply on staging and repeat the staging check in
`docs/ROLLOUT_SHARING_AND_SETTINGS.md` with two members and one non-member.

## 6. Code changes (when approved)

- `server.py`: bootstrap creates and joins the organization; `create_user` and the import join
  the caller's organization; registration follows Decision 1; admin endpoints to add or remove a
  member; `_serialize_user` already returns `organization_id`.
- `config/settings.py`: `INSTITUTION_NAME`, `INSTITUTION_EMAIL_DOMAINS`, `REGISTRATION_ENABLED`.
- `frontend/app/admin/page.tsx`: the "Member" column and the add/remove action.
- `alembic/versions/…_add_institution_membership.py` plus the dry-run script.
- No change to `sharing.py` or `academic_access.py`: they already do the right thing once
  `organization_id` is set.

## 7. Tests

- Each creation path sets (or deliberately does not set) membership.
- Two members can share by name and with "Everyone in your organization"; a non-member sees
  neither; a removed member loses access to org-wide shares but keeps their own work.
- A member can create a term and a course; a non-member gets the clear 400.
- Migration: upgrade on a database with none, one and two organizations (the last must stop);
  downgrade restores exactly the previous `organization_id` values.

## 8. Decisions (made 13 Nov 2026)

1. **Self-registration:** stays open; verified addresses on `INSTITUTION_EMAIL_DOMAINS` join
   automatically, anyone else is a non-member until an admin adds them.
2. **Institution:** rename the existing organization (e.g. the seeded "Demo University") to
   `INSTITUTION_NAME`; create one only when none exists.
3. **Existing users:** only active users on `INSTITUTION_EMAIL_DOMAINS` join; with no domains
   set, nobody does.
4. **Removal:** what a removed member shared stays shared; they stop seeing organization-wide
   shares.

## 9. Risks

- **Over-sharing on backfill:** joining the wrong accounts exposes everything already shared with
  "Everyone in your organization". The domain rule and the dry run exist to prevent this.
- **Admin reach changes:** admins with an organization see that organization's courses instead of
  all courses (`academic_access.can_read_course`). With one organization, the same set.
- **Privacy review:** this changes who can see student work. It belongs in the Information Risk
  Assessment before the pilot.

## 10. Rollout of step 1 (migration `u4v5w6x7y8z9`)

1. Back up the database.
2. Set, in the backend's environment (the same place as `DATABASE_URL`):
   `INSTITUTION_NAME="University of Toronto"` and `INSTITUTION_EMAIL_DOMAINS=utoronto.ca`
   (comma-separated for several; a subdomain such as `mail.utoronto.ca` must be listed itself).
3. Dry run, and read the result before going on:
   `python scripts/institution_membership_dry_run.py` (add `--list` to see who would join).
4. `alembic upgrade head`, then repeat the dry run: it should report nobody left to join.
5. Undo, if needed: `alembic downgrade t3u4v5w6x7y8` restores exactly the previous names and
   memberships.

Step 1 only sets memberships for existing accounts. New accounts join once step 2 (the
creation paths) ships.
