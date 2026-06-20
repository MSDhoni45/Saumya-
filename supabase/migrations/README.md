# Supabase migrations — WhatsAgent AI

Ordered SQL migrations implementing the canonical `businesses` schema. Apply with
the Supabase CLI:

```bash
supabase link --project-ref <project-ref>
supabase db push
```

For local dev:

```bash
supabase start
supabase db reset   # applies all migrations in filename order
```

In production, the API container runs them via `docker-entrypoint.sh` under an
advisory lock (id `87412001`) when `RUN_MIGRATIONS=1`.

## Order & contents

| File | Contents |
|---|---|
| `20260608130001_extensions_and_helpers.sql` | `pgcrypto`, `vector` extensions; `set_updated_at()` trigger |
| `20260608130002_businesses_and_users.sql` | `businesses`, `users`, membership |
| `20260608130003_whatsapp_accounts.sql` | `whatsapp_accounts` (encrypted tokens) |
| `20260608130004_conversations_and_messages.sql` | `conversations`, `messages` (+ triggers) |
| `20260608130005_leads_and_appointments.sql` | `leads`, `appointments` |
| `20260608130006_knowledge_base_and_documents.sql` | `documents`, `document_chunks` (pgvector) |
| `20260608130007_followup_sequences.sql` | `followup_sequences`, `followup_enrollments` |
| `20260608130008_row_level_security.sql` | `is_business_member` helpers + RLS policies |
| `20260608140001_ai_agents_and_lead_qualification.sql` | `ai_agents`, `ai_interactions`, lead qualification |
| `20260608140002_auth_rbac_roles.sql` | RBAC roles + helpers |
| `20260609000001_business_onboarding_completed.sql` | onboarding flag |
| `20260609000002_billing.sql` | Stripe / Razorpay billing tables |
| `20260609000003_team_invites.sql` | team invite flow |
| `20260611000001_document_chunks.sql` | `document_chunks` ivfflat index tuning |
| `20260611000002_message_status_callbacks.sql` | WhatsApp delivery callbacks |
| `20260611000003_document_status_canonical.sql` | canonical document status enum |
| `20260612000001_ai_interactions_inbound_unique.sql` | UNIQUE on `inbound_message_id` for outbound idempotency |
| `20260612000002_operator_alerts.sql` | `operator_alerts` for `SEND_FAILED` / `STATUS_FAILED` |

## Notes

- **Tenant isolation**: every tenant table carries `business_id`, RLS enabled.
  Membership/role checks go through `SECURITY DEFINER` helpers
  (`is_business_member`, etc.) to avoid RLS recursion.
- **Service role**: API uses Supabase service role for trusted server-side
  writes. Bypasses RLS by design — backend scopes `business_id` in app code via
  `db_context`. Tables like `document_chunks`, `ai_interactions`, `audit_logs`
  intentionally have no user-facing write policies.
- **Embeddings**: `document_chunks.embedding` is `vector(1536)`, matching
  `text-embedding-3-small`. Change the column + rebuild `ivfflat` if model
  changes.
- **Encrypted secrets**: `*_token_encrypted` columns are `bytea`; encrypt with
  Fernet (`TOKEN_ENCRYPTION_KEY`) at the application layer.
