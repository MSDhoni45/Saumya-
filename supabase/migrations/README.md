# Supabase migrations — WhatsAgent AI

Ordered SQL migrations implementing the schema described in
[`/docs/architecture/02-database-schema.md`](../../docs/architecture/02-database-schema.md).
Apply with the Supabase CLI:

```bash
supabase link --project-ref <project-ref>
supabase db push
```

or, for local development:

```bash
supabase start
supabase db reset   # applies all migrations in this folder, in filename order
```

## Order & contents

| File | Contents |
|---|---|
| `20260608120001_extensions_and_helpers.sql` | `pgcrypto`, `vector` extensions; generic `set_updated_at()` trigger function |
| `20260608120002_enums.sql` | All enumerated types used across the schema |
| `20260608120003_organizations_and_profiles.sql` | `organizations`, `profiles` (+ auto-create-on-signup trigger), `organization_members` |
| `20260608120004_whatsapp_and_messaging.sql` | `whatsapp_connections`, `contacts`, `conversations`, `messages` (+ idempotency & last-message-at triggers) |
| `20260608120005_knowledge_base.sql` | `knowledge_base_documents`, `knowledge_base_chunks` (pgvector embeddings + ivfflat index) |
| `20260608120006_ai_agents.sql` | `ai_agents`, `ai_interactions` |
| `20260608120007_crm_leads.sql` | `leads` (+ stage-change trigger), `lead_activities` |
| `20260608120008_appointments_and_calendar.sql` | `calendar_connections`, `appointments` |
| `20260608120009_follow_ups.sql` | `follow_up_sequences`, `follow_up_steps`, `follow_up_enrollments` |
| `20260608120010_analytics_and_audit.sql` | `analytics_daily_stats`, `audit_logs` |
| `20260608120011_row_level_security.sql` | `is_org_member` / `is_org_admin` / `is_org_owner` helper functions + RLS policies for every table |

## Notes

- **Tenant isolation**: every tenant table carries `organization_id` and has
  RLS enabled. Membership/role checks go through `SECURITY DEFINER` helper
  functions (`is_org_member`, `is_org_admin`, `is_org_owner`) to avoid RLS
  recursion when checking `organization_members` from policies on other
  tables (and on itself).
- **Service role**: the FastAPI backend uses the Supabase **service role**
  for trusted server-side writes (webhook ingestion, AI replies, schedulers,
  analytics rollups). The service role bypasses RLS by design — the backend
  performs its own `organization_id` scoping in application code. Tables such
  as `knowledge_base_chunks`, `ai_interactions`, `analytics_daily_stats`, and
  `audit_logs` intentionally have **no write policies** for regular users —
  they are written only by the service role.
- **Embeddings**: `knowledge_base_chunks.embedding` is `vector(1536)`,
  matching OpenAI's `text-embedding-3-small` / `text-embedding-ada-002`. If a
  different embedding model is chosen, update the column dimension and rebuild
  the `ivfflat` index (and re-tune its `lists` parameter as the corpus grows).
- **Encrypted secrets**: `access_token_encrypted` / `refresh_token_encrypted`
  columns are `bytea`. Encrypt/decrypt at the application layer (e.g.
  AES-GCM with a key from your secrets manager) before reading/writing —
  do not store plaintext tokens.
- **Auto profile creation**: a trigger on `auth.users` creates a matching
  `profiles` row on signup, seeded from `raw_user_meta_data` (`full_name`,
  `avatar_url`).
