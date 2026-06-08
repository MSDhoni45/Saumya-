-- =============================================================================
-- WhatsAgent AI — Migration 11: Row Level Security
--
-- Strategy
-- --------
-- Every tenant-scoped table is keyed by organization_id and protected by RLS.
-- Two SECURITY DEFINER helper functions encapsulate the membership check so
-- policies stay short and — critically — so checking membership from a policy
-- on `organization_members` itself does not recurse into RLS again.
--
-- The FastAPI backend connects with the Supabase service role for trusted
-- server-side writes (webhook ingestion, AI replies, schedulers, analytics
-- rollups) and bypasses RLS by design — it performs its own org-scoping in
-- application code. These policies are the defense-in-depth layer that also
-- allows the frontend to query Supabase directly wherever useful.
--
-- Tables with NO write policy for a given operation are intentionally
-- writable only by the service role (e.g. knowledge_base_chunks,
-- ai_interactions, analytics_daily_stats, audit_logs).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Helper functions
-- -----------------------------------------------------------------------------
create or replace function public.is_org_member(target_org_id uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_members om
    where om.organization_id = target_org_id
      and om.user_id = auth.uid()
      and om.status = 'active'
  );
$$;

create or replace function public.is_org_admin(target_org_id uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_members om
    where om.organization_id = target_org_id
      and om.user_id = auth.uid()
      and om.status = 'active'
      and om.role in ('owner', 'admin')
  );
$$;

create or replace function public.is_org_owner(target_org_id uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_members om
    where om.organization_id = target_org_id
      and om.user_id = auth.uid()
      and om.status = 'active'
      and om.role = 'owner'
  );
$$;

comment on function public.is_org_member(uuid) is
  'True if the current JWT user is an active member of the given organization.';
comment on function public.is_org_admin(uuid) is
  'True if the current JWT user is an active owner/admin of the given organization.';
comment on function public.is_org_owner(uuid) is
  'True if the current JWT user is the active owner of the given organization.';

-- =============================================================================
-- organizations
-- =============================================================================
alter table public.organizations enable row level security;

create policy organizations_select_members
  on public.organizations for select
  using (public.is_org_member(id));

-- Any authenticated user may create an organization (they become its owner
-- via the application bootstrap flow, which also inserts the membership row).
create policy organizations_insert_authenticated
  on public.organizations for insert
  to authenticated
  with check (auth.uid() is not null);

create policy organizations_update_admins
  on public.organizations for update
  using (public.is_org_admin(id))
  with check (public.is_org_admin(id));

create policy organizations_delete_owner
  on public.organizations for delete
  using (public.is_org_owner(id));

-- =============================================================================
-- profiles
-- =============================================================================
alter table public.profiles enable row level security;

create policy profiles_select_self_or_org_mates
  on public.profiles for select
  using (
    id = auth.uid()
    or exists (
      select 1
      from public.organization_members mine
      join public.organization_members theirs
        on theirs.organization_id = mine.organization_id
      where mine.user_id = auth.uid()
        and mine.status = 'active'
        and theirs.user_id = profiles.id
        and theirs.status = 'active'
    )
  );

create policy profiles_insert_self
  on public.profiles for insert
  to authenticated
  with check (id = auth.uid());

create policy profiles_update_self
  on public.profiles for update
  using (id = auth.uid())
  with check (id = auth.uid());

-- =============================================================================
-- organization_members
-- =============================================================================
alter table public.organization_members enable row level security;

create policy org_members_select_members
  on public.organization_members for select
  using (public.is_org_member(organization_id));

create policy org_members_insert_admins
  on public.organization_members for insert
  with check (public.is_org_admin(organization_id));

create policy org_members_update_admins
  on public.organization_members for update
  using (public.is_org_admin(organization_id))
  with check (public.is_org_admin(organization_id));

create policy org_members_delete_admins
  on public.organization_members for delete
  using (public.is_org_admin(organization_id));

-- =============================================================================
-- whatsapp_connections  (sensitive — admin-managed)
-- =============================================================================
alter table public.whatsapp_connections enable row level security;

create policy whatsapp_connections_select_members
  on public.whatsapp_connections for select
  using (public.is_org_member(organization_id));

create policy whatsapp_connections_insert_admins
  on public.whatsapp_connections for insert
  with check (public.is_org_admin(organization_id));

create policy whatsapp_connections_update_admins
  on public.whatsapp_connections for update
  using (public.is_org_admin(organization_id))
  with check (public.is_org_admin(organization_id));

create policy whatsapp_connections_delete_admins
  on public.whatsapp_connections for delete
  using (public.is_org_admin(organization_id));

-- =============================================================================
-- contacts
-- =============================================================================
alter table public.contacts enable row level security;

create policy contacts_select_members
  on public.contacts for select
  using (public.is_org_member(organization_id));

create policy contacts_insert_members
  on public.contacts for insert
  with check (public.is_org_member(organization_id));

create policy contacts_update_members
  on public.contacts for update
  using (public.is_org_member(organization_id))
  with check (public.is_org_member(organization_id));

create policy contacts_delete_admins
  on public.contacts for delete
  using (public.is_org_admin(organization_id));

-- =============================================================================
-- conversations
-- =============================================================================
alter table public.conversations enable row level security;

create policy conversations_select_members
  on public.conversations for select
  using (public.is_org_member(organization_id));

create policy conversations_insert_members
  on public.conversations for insert
  with check (public.is_org_member(organization_id));

create policy conversations_update_members
  on public.conversations for update
  using (public.is_org_member(organization_id))
  with check (public.is_org_member(organization_id));

create policy conversations_delete_admins
  on public.conversations for delete
  using (public.is_org_admin(organization_id));

-- =============================================================================
-- messages
--   Members can read the thread and send replies; corrections to delivery
--   status, edits, and deletions are reserved for the service role (webhook
--   ingestion / moderation), so no UPDATE/DELETE policy is granted here.
-- =============================================================================
alter table public.messages enable row level security;

create policy messages_select_members
  on public.messages for select
  using (public.is_org_member(organization_id));

create policy messages_insert_members
  on public.messages for insert
  with check (public.is_org_member(organization_id));

-- =============================================================================
-- knowledge_base_documents
-- =============================================================================
alter table public.knowledge_base_documents enable row level security;

create policy kb_documents_select_members
  on public.knowledge_base_documents for select
  using (public.is_org_member(organization_id));

create policy kb_documents_insert_members
  on public.knowledge_base_documents for insert
  with check (public.is_org_member(organization_id));

create policy kb_documents_update_admins
  on public.knowledge_base_documents for update
  using (public.is_org_admin(organization_id))
  with check (public.is_org_admin(organization_id));

create policy kb_documents_delete_admins
  on public.knowledge_base_documents for delete
  using (public.is_org_admin(organization_id));

-- =============================================================================
-- knowledge_base_chunks
--   Read-only to org members (e.g. for a "what does the AI know" inspector
--   UI). All writes happen via the ingestion worker using the service role.
-- =============================================================================
alter table public.knowledge_base_chunks enable row level security;

create policy kb_chunks_select_members
  on public.knowledge_base_chunks for select
  using (public.is_org_member(organization_id));

-- =============================================================================
-- ai_agents
-- =============================================================================
alter table public.ai_agents enable row level security;

create policy ai_agents_select_members
  on public.ai_agents for select
  using (public.is_org_member(organization_id));

create policy ai_agents_insert_admins
  on public.ai_agents for insert
  with check (public.is_org_admin(organization_id));

create policy ai_agents_update_admins
  on public.ai_agents for update
  using (public.is_org_admin(organization_id))
  with check (public.is_org_admin(organization_id));

create policy ai_agents_delete_admins
  on public.ai_agents for delete
  using (public.is_org_admin(organization_id));

-- =============================================================================
-- ai_interactions  (read-only log; written by the backend via service role)
-- =============================================================================
alter table public.ai_interactions enable row level security;

create policy ai_interactions_select_members
  on public.ai_interactions for select
  using (public.is_org_member(organization_id));

-- =============================================================================
-- leads
-- =============================================================================
alter table public.leads enable row level security;

create policy leads_select_members
  on public.leads for select
  using (public.is_org_member(organization_id));

create policy leads_insert_members
  on public.leads for insert
  with check (public.is_org_member(organization_id));

create policy leads_update_members
  on public.leads for update
  using (public.is_org_member(organization_id))
  with check (public.is_org_member(organization_id));

create policy leads_delete_admins
  on public.leads for delete
  using (public.is_org_admin(organization_id));

-- =============================================================================
-- lead_activities
-- =============================================================================
alter table public.lead_activities enable row level security;

create policy lead_activities_select_members
  on public.lead_activities for select
  using (public.is_org_member(organization_id));

create policy lead_activities_insert_members
  on public.lead_activities for insert
  with check (public.is_org_member(organization_id));

create policy lead_activities_update_admins
  on public.lead_activities for update
  using (public.is_org_admin(organization_id))
  with check (public.is_org_admin(organization_id));

create policy lead_activities_delete_admins
  on public.lead_activities for delete
  using (public.is_org_admin(organization_id));

-- =============================================================================
-- calendar_connections  (sensitive — admin-managed)
-- =============================================================================
alter table public.calendar_connections enable row level security;

create policy calendar_connections_select_members
  on public.calendar_connections for select
  using (public.is_org_member(organization_id));

create policy calendar_connections_insert_admins
  on public.calendar_connections for insert
  with check (public.is_org_admin(organization_id));

create policy calendar_connections_update_admins
  on public.calendar_connections for update
  using (public.is_org_admin(organization_id))
  with check (public.is_org_admin(organization_id));

create policy calendar_connections_delete_admins
  on public.calendar_connections for delete
  using (public.is_org_admin(organization_id));

-- =============================================================================
-- appointments
-- =============================================================================
alter table public.appointments enable row level security;

create policy appointments_select_members
  on public.appointments for select
  using (public.is_org_member(organization_id));

create policy appointments_insert_members
  on public.appointments for insert
  with check (public.is_org_member(organization_id));

create policy appointments_update_members
  on public.appointments for update
  using (public.is_org_member(organization_id))
  with check (public.is_org_member(organization_id));

create policy appointments_delete_admins
  on public.appointments for delete
  using (public.is_org_admin(organization_id));

-- =============================================================================
-- follow_up_sequences
-- =============================================================================
alter table public.follow_up_sequences enable row level security;

create policy follow_up_sequences_select_members
  on public.follow_up_sequences for select
  using (public.is_org_member(organization_id));

create policy follow_up_sequences_insert_admins
  on public.follow_up_sequences for insert
  with check (public.is_org_admin(organization_id));

create policy follow_up_sequences_update_admins
  on public.follow_up_sequences for update
  using (public.is_org_admin(organization_id))
  with check (public.is_org_admin(organization_id));

create policy follow_up_sequences_delete_admins
  on public.follow_up_sequences for delete
  using (public.is_org_admin(organization_id));

-- =============================================================================
-- follow_up_steps
--   Scoped through the parent sequence's organization_id (this table has no
--   organization_id column of its own).
-- =============================================================================
alter table public.follow_up_steps enable row level security;

create policy follow_up_steps_select_members
  on public.follow_up_steps for select
  using (
    exists (
      select 1 from public.follow_up_sequences seq
      where seq.id = follow_up_steps.sequence_id
        and public.is_org_member(seq.organization_id)
    )
  );

create policy follow_up_steps_write_admins
  on public.follow_up_steps for all
  using (
    exists (
      select 1 from public.follow_up_sequences seq
      where seq.id = follow_up_steps.sequence_id
        and public.is_org_admin(seq.organization_id)
    )
  )
  with check (
    exists (
      select 1 from public.follow_up_sequences seq
      where seq.id = follow_up_steps.sequence_id
        and public.is_org_admin(seq.organization_id)
    )
  );

-- =============================================================================
-- follow_up_enrollments
-- =============================================================================
alter table public.follow_up_enrollments enable row level security;

create policy follow_up_enrollments_select_members
  on public.follow_up_enrollments for select
  using (public.is_org_member(organization_id));

create policy follow_up_enrollments_write_admins
  on public.follow_up_enrollments for all
  using (public.is_org_admin(organization_id))
  with check (public.is_org_admin(organization_id));

-- =============================================================================
-- analytics_daily_stats  (read-only; populated by the analytics worker)
-- =============================================================================
alter table public.analytics_daily_stats enable row level security;

create policy analytics_daily_stats_select_members
  on public.analytics_daily_stats for select
  using (public.is_org_member(organization_id));

-- =============================================================================
-- audit_logs  (sensitive — admins/owners only; append-only via service role)
-- =============================================================================
alter table public.audit_logs enable row level security;

create policy audit_logs_select_admins
  on public.audit_logs for select
  using (public.is_org_admin(organization_id));
