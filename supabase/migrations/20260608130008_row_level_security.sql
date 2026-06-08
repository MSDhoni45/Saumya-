-- Helper functions ----------------------------------------------------------
-- SECURITY DEFINER so they can read `users` regardless of the caller's row
-- visibility — this avoids recursive-policy evaluation on `users` itself.
create or replace function auth_business_id()
returns uuid
language sql
security definer
stable
set search_path = public
as $$
  select business_id from users where id = auth.uid();
$$;

create or replace function auth_is_business_admin()
returns boolean
language sql
security definer
stable
set search_path = public
as $$
  select exists (
    select 1 from users
     where id = auth.uid()
       and role in ('owner', 'admin')
  );
$$;

-- Enable RLS on every tenant-scoped table -------------------------------------
alter table businesses          enable row level security;
alter table users               enable row level security;
alter table whatsapp_accounts   enable row level security;
alter table conversations       enable row level security;
alter table messages            enable row level security;
alter table leads               enable row level security;
alter table appointments        enable row level security;
alter table knowledge_base      enable row level security;
alter table documents           enable row level security;
alter table followup_sequences  enable row level security;

-- businesses ------------------------------------------------------------------
create policy businesses_select_own on businesses
  for select using (id = auth_business_id());

create policy businesses_update_admin on businesses
  for update
  using (id = auth_business_id() and auth_is_business_admin())
  with check (id = auth_business_id() and auth_is_business_admin());

-- users -----------------------------------------------------------------------
create policy users_select_same_business on users
  for select using (business_id = auth_business_id());

create policy users_update_self on users
  for update
  using (id = auth.uid())
  with check (id = auth.uid());

create policy users_update_admin on users
  for update
  using (business_id = auth_business_id() and auth_is_business_admin())
  with check (business_id = auth_business_id() and auth_is_business_admin());

-- whatsapp_accounts -------------------------------------------------------------
create policy whatsapp_accounts_select on whatsapp_accounts
  for select using (business_id = auth_business_id());

create policy whatsapp_accounts_write_admin on whatsapp_accounts
  for all
  using (business_id = auth_business_id() and auth_is_business_admin())
  with check (business_id = auth_business_id() and auth_is_business_admin());

-- conversations -----------------------------------------------------------------
create policy conversations_select on conversations
  for select using (business_id = auth_business_id());

create policy conversations_write on conversations
  for all
  using (business_id = auth_business_id())
  with check (business_id = auth_business_id());

-- messages ----------------------------------------------------------------------
create policy messages_select on messages
  for select using (business_id = auth_business_id());

create policy messages_insert on messages
  for insert
  with check (business_id = auth_business_id());

-- leads -------------------------------------------------------------------------
create policy leads_select on leads
  for select using (business_id = auth_business_id());

create policy leads_write on leads
  for all
  using (business_id = auth_business_id())
  with check (business_id = auth_business_id());

-- appointments ------------------------------------------------------------------
create policy appointments_select on appointments
  for select using (business_id = auth_business_id());

create policy appointments_write on appointments
  for all
  using (business_id = auth_business_id())
  with check (business_id = auth_business_id());

-- knowledge_base ----------------------------------------------------------------
create policy knowledge_base_select on knowledge_base
  for select using (business_id = auth_business_id());

create policy knowledge_base_write_admin on knowledge_base
  for all
  using (business_id = auth_business_id() and auth_is_business_admin())
  with check (business_id = auth_business_id() and auth_is_business_admin());

-- documents ---------------------------------------------------------------------
create policy documents_select on documents
  for select using (business_id = auth_business_id());

create policy documents_write_admin on documents
  for all
  using (business_id = auth_business_id() and auth_is_business_admin())
  with check (business_id = auth_business_id() and auth_is_business_admin());

-- followup_sequences --------------------------------------------------------------
create policy followup_sequences_select on followup_sequences
  for select using (business_id = auth_business_id());

create policy followup_sequences_write_admin on followup_sequences
  for all
  using (business_id = auth_business_id() and auth_is_business_admin())
  with check (business_id = auth_business_id() and auth_is_business_admin());

-- Note: Supabase's `service_role` carries BYPASSRLS, so backend/worker
-- writes via the service-role key bypass these policies entirely — no
-- explicit service-role policies are needed.
