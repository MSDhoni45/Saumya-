-- Replace the placeholder owner/admin/agent role set with the product's
-- actual RBAC model: super_admin (platform operator, not bound to a single
-- business), business_admin (manages their business end-to-end), team_member
-- (day-to-day operator within a business).

-- Remap any existing rows before tightening the constraint (safe no-op on a
-- fresh database — neither schema has been deployed to a live project yet).
update users set role = 'business_admin' where role in ('owner', 'admin');
update users set role = 'team_member' where role = 'agent';

alter table users drop constraint if exists users_role_check;
alter table users
  add constraint users_role_check
  check (role in ('super_admin', 'business_admin', 'team_member'));

-- New self-serve signups bootstrap their own business and become its admin;
-- super_admin is a platform-operator role granted out-of-band (never via signup).
alter table users alter column role set default 'business_admin';

-- RLS helpers ----------------------------------------------------------------
-- super_admin is platform-wide and intentionally NOT business-scoped — the
-- backend enforces super_admin access at the application layer (it already
-- holds the service-role key, which carries BYPASSRLS) rather than threading
-- a "see every business" clause through every RLS policy.
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
       and role = 'business_admin'
  );
$$;

create or replace function auth_is_super_admin()
returns boolean
language sql
security definer
stable
set search_path = public
as $$
  select exists (
    select 1 from users
     where id = auth.uid()
       and role = 'super_admin'
  );
$$;
