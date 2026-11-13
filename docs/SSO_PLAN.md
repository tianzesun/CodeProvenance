# Plan: sign-in with UTORid / Microsoft Entra ID (after the pilot)

**Status:** plan for review, not started. **Risk:** high (authentication). The pilot runs on the
built-in accounts, hardened in #48 (Argon2id, sessions end on password change, 7-day cap).

## 1. Why

The built-in login makes IntegrityDesk responsible for passwords, resets, verification email and
offboarding. Signing in with U of T accounts instead gives:

- institutional identities, the institution's multi-factor authentication and conditional access;
- offboarding for free: an account disabled centrally can no longer sign in;
- membership from identity rather than email domain: a user from U of T's tenant **is** a member
  (replaces `INSTITUTION_EMAIL_DOMAINS`, docs/ORGANIZATION_MEMBERSHIP_DESIGN.md);
- no stored passwords for most users.

## 2. Approach

- **Protocol: OpenID Connect**, authorization-code flow with PKCE, against U of T's Microsoft Entra
  ID tenant (single-tenant app registration: no other organization's accounts can sign in). If U of T
  prefers its UTORid SAML login for this app, the same plan applies with SAML in place of OIDC;
  **confirm with U of T's central identity team which one they want**.
- **Scopes:** `openid profile email` only. No Microsoft Graph access is needed.
- **Library:** a maintained OIDC client (e.g. Authlib or MSAL for Python). **A new dependency, to be
  approved when the work starts.**
- **Sessions stay as they are:** after the identity provider returns, IntegrityDesk issues its own
  session cookie (the #48 token with `auth_time` and fingerprint). The 7-day cap still applies; a
  shorter cap, or re-checking with the provider on refresh, may be wanted (decision 3).

## 3. Identity and accounts

- **Key users on the provider's immutable id** (`tid` + `oid` for Entra), not email: email
  addresses change. New nullable column `users.external_subject` (unique), so this needs a
  migration with a rollback.
- **First SSO sign-in of an existing account:** link it once, by the verified email claim, to the
  existing user (keeping their courses, analyses and cases); from then on match on
  `external_subject` only. Accounts whose email does not match anything are created as members.
- **SSO users have no password:** store an unusable random Argon2id hash (the column stays NOT
  NULL); password login and reset are refused for them.
- **Roles:** keep roles managed in the admin page (decision 2), or map Entra app roles, e.g. an
  `IntegrityDesk.Admin` role assigned by U of T.

## 4. Turning off the built-in login

1. SSO goes live alongside password login; users are asked to switch.
2. Once everyone has linked, password sign-in, self-registration and password reset are turned off
   for accounts in the institution (new settings, default on until then).
3. Keep **one break-glass local admin** (Argon2id, long random password in the managed secret store)
   for when the identity provider is unavailable.
4. Guest demo sessions are unaffected (or turned off, `GUEST_LOGIN_ENABLED`).

## 5. What U of T needs to provide

- An Entra ID app registration (or the SAML equivalent): client id, tenant id, redirect URI
  `https://<host>/api/auth/sso/callback`, and a client secret or certificate kept in the managed
  secret store (never in the repository or `.env` files in git).
- Which users may sign in (all of the tenant, or a group), and any conditional-access/MFA policy.
- The Information Risk Assessment covering the app, updated for SSO.

## 6. Work breakdown (each its own PR)

| Step | Change | Risk |
|---|---|---|
| 1 | Migration: `users.external_subject` (unique, nullable) with rollback | schema |
| 2 | OIDC login + callback endpoints, state/nonce/PKCE, single-tenant check, account linking | auth |
| 3 | Login page: "Sign in with UTORid" button; password form behind a setting | UI |
| 4 | Settings to turn off password login/registration/reset for institution accounts; break-glass admin | auth |
| 5 | Offboarding: sessions of a user disabled centrally end within the cap (or on refresh) | auth |
| 6 | Docs: rollout and staging check (two UTORid users, one non-U of T account refused) | docs |

## 7. Decisions needed

1. **OIDC (Entra ID) or SAML (UTORid)**: U of T's identity team's preference.
2. **Roles:** keep in the admin page, or take from Entra app roles?
3. **Session length for SSO users:** keep 7 days, shorten (e.g. 24 h), or re-validate with the
   provider on every refresh?
4. **Who may sign in:** the whole tenant, or only a group (e.g. teaching staff)?
5. **Timing:** after the pilot, and before any second department joins.

## 8. Risks

- **Account linking by email** is the one moment an email decides identity: done once, only from
  the provider's verified email claim, and logged. A mismatch creates a new account rather than
  guessing.
- **Provider outage** locks everyone out except the break-glass admin.
- **Redirect and state handling** are where OIDC integrations usually go wrong: exact redirect
  URIs, state and nonce checked, PKCE, no tokens in URLs or logs.
