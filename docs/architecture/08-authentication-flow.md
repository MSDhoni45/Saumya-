# 8. Authentication Flow

WhatsAgent AI delegates **identity** (passwords, sessions, password resets,
email verification) entirely to **Supabase Auth**. The custom backend never
touches credentials — it only validates issued JWTs and layers on
**organization membership/roles**, which Supabase Auth knows nothing about.

## 8.1 Components involved

- **Supabase Auth** — issues/refreshes JWTs, sends auth emails (verification,
  password reset, invites), exposes a JWKS endpoint for token validation.
- **Next.js frontend** — talks to Supabase Auth directly via `@supabase/ssr`
  (cookie-based sessions for App Router), calls FastAPI for everything else.
- **FastAPI backend** — validates JWTs on every request, resolves the active
  organization + role, and owns the one custom step Supabase doesn't know
  about: turning a brand-new user into an **organization owner**.

## 8.2 Signup flow

```
User submits signup form (email, password, business name)
        │
        ▼
Frontend → supabase.auth.signUp({ email, password, options: { data: { full_name } } })
        │                                            │
        │                                            ▼
        │                          Supabase creates auth.users row
        │                          → DB trigger creates `profiles` row (migration 03)
        │                          → sends verification email (if enabled)
        ▼
Frontend receives a session (or "check your email" state if email
confirmation is required)
        │
        ▼
Frontend calls FastAPI: POST /api/v1/auth/bootstrap { org_name }
   Authorization: Bearer <supabase_jwt>
        │
        ▼
FastAPI: validates JWT → user_id
   - profiles row already exists (created by DB trigger)
   - INSERT organizations (name = org_name, slug = generated)
   - INSERT organization_members (org, user_id, role = 'owner', status = 'active')
   - INSERT audit_logs ('organization.created')
        │
        ▼
Returns { organization, membership } → frontend redirects to the dashboard
```

`/auth/bootstrap` is **idempotent**: if the user already owns/belongs to an
organization (e.g. they refresh mid-flow, or accepted an invite before
finishing signup), it returns the existing membership rather than creating a
duplicate. This is the *only* custom write in the signup path — everything
else is Supabase Auth + a DB trigger.

## 8.3 Login flow

```
User submits email + password
        │
        ▼
Frontend → supabase.auth.signInWithPassword({ email, password })
        │
        ▼
Supabase validates credentials, returns { access_token, refresh_token, user }
        │
        ▼
Frontend persists the session via @supabase/ssr cookie helpers
(httpOnly cookies, refreshed by middleware on each request)
        │
        ▼
Frontend → GET /api/v1/auth/me   (Authorization: Bearer <access_token>)
        │
        ▼
FastAPI validates JWT, returns { profile, organizations: [{ organization, role }] }
        │
        ▼
Frontend selects the active organization (last used, or the only one)
and stores it (e.g. in a cookie/localStorage) — sent as `X-Org-Id` on
every subsequent FastAPI request
```

Token refresh is handled transparently by the Supabase client/middleware
(`@supabase/ssr` refreshes the session cookie on the server before it expires);
FastAPI never issues or refreshes tokens itself.

## 8.4 Password reset flow

```
User clicks "Forgot password?" and submits their email
        │
        ▼
Frontend → supabase.auth.resetPasswordForEmail(email, { redirectTo: <reset-page-url> })
        │
        ▼
Supabase sends a reset email with a one-time link to <reset-page-url>#access_token=...
        │
        ▼
User opens the link → frontend reset-password page extracts the recovery
session (supabase.auth.onAuthStateChange "PASSWORD_RECOVERY" event)
        │
        ▼
User submits a new password
        │
        ▼
Frontend → supabase.auth.updateUser({ password: newPassword })
        │
        ▼
Supabase updates the credential; user is signed in with the new password
```

No FastAPI involvement — this is fully handled by Supabase Auth + a
dedicated Next.js route (`app/(auth)/reset-password/page.tsx`).

## 8.5 Team invites (the one place auth and orgs intersect)

```
Admin: POST /api/v1/auth/organizations/{org_id}/invite { email, role }
        │
        ▼
FastAPI (admin-only):
   - INSERT organization_members (invited_email = email, status = 'invited', role)
   - Triggers an invite email — either:
       a) supabase.auth.admin.inviteUserByEmail(email)  [Supabase sends a
          signup-with-magic-link email], or
       b) a transactional email containing a link to /accept-invite?token=...
        │
        ▼
Invitee clicks the link → completes Supabase signup/login (creating
auth.users + profiles, same trigger as §8.2) → lands on /accept-invite
        │
        ▼
Frontend → POST /api/v1/auth/invites/accept { invite_token }
        │
        ▼
FastAPI: resolves the pending organization_members row by invited_email
(matched against the now-authenticated user's email), sets
user_id = auth.uid(), status = 'active'
```

## 8.6 Request-time validation (every authenticated FastAPI call)

```
Incoming request
   Authorization: Bearer <jwt>
   X-Org-Id: <organization_uuid>
        │
        ▼
[Dependency] get_current_user
   - Fetches/caches Supabase JWKS (refreshed periodically, not per-request)
   - Verifies signature, expiry, issuer, audience
   - Extracts { user_id, email } → AuthenticatedUser
   - 401 Unauthorized on any failure
        │
        ▼
[Dependency] get_current_organization
   - Looks up organization_members WHERE org_id = X-Org-Id AND user_id = user_id
     AND status = 'active'
   - 403 Forbidden if no active membership; 400 if X-Org-Id missing/malformed
   - Returns OrganizationContext { organization_id, role }
        │
        ▼
[Dependency] require_role("admin")   (only on admin-gated routes)
   - 403 Forbidden if role not in {owner, admin}
        │
        ▼
Router handler executes with (db, current_user, org_context)
```

JWKS keys are fetched once at startup and refreshed on a background interval
(and on a verification failure that looks like key rotation), so steady-state
validation is a pure in-process cryptographic check — no per-request network
call to Supabase.

## 8.7 Why this split is the right call

- **Security**: password storage, hashing, brute-force protection, email
  deliverability, and session/token rotation are Supabase's responsibility —
  exactly the kind of thing you don't want to hand-roll in a young product.
- **Simplicity**: the frontend gets first-class Supabase SDK support
  (cookie-based SSR sessions, `onAuthStateChange`, automatic refresh) with
  zero custom plumbing.
- **Clean separation**: FastAPI's auth surface area shrinks to "validate a
  token and resolve an organization" — a small, well-tested dependency chain
  reused by every route — plus the one genuinely product-specific concern
  (organizations, roles, invites) that Supabase Auth has no concept of.

## 8.8 Role model recap

| Role | Can do |
|---|---|
| `owner` | Everything `admin` can, plus: delete the organization, transfer ownership, manage billing |
| `admin` | Manage WhatsApp/Calendar connections, AI agents, knowledge base, follow-up sequences, team members/invites, delete leads/conversations/appointments |
| `agent` | Day-to-day work: view/respond to conversations, manage leads (create/update/notes), book/reschedule appointments, view analytics — cannot touch connections, agent config, or team membership |

Enforced at two layers: FastAPI's `require_role` dependency (primary,
descriptive 403s) and Postgres RLS policies (`is_org_admin`/`is_org_owner`,
defense-in-depth — see migration `20260608120011_row_level_security.sql`).
