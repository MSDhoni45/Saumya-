-- =============================================================================
-- Add onboarding_completed flag to businesses
-- =============================================================================

alter table public.businesses
  add column if not exists onboarding_completed boolean not null default false;

-- Existing businesses have already been set up manually — mark them complete
-- so they are not forced back through the onboarding wizard.
update public.businesses set onboarding_completed = true;
