-- =============================================================================
-- WhatsAgent AI — Migration 01: Extensions & shared helpers
-- =============================================================================

-- gen_random_uuid() and encryption helpers (for token-at-rest encryption)
create extension if not exists "pgcrypto";

-- Vector embeddings for the Knowledge Base / RAG pipeline
create extension if not exists "vector";

-- -----------------------------------------------------------------------------
-- Generic "updated_at" maintenance trigger, reused by every table that has
-- an updated_at column.
-- -----------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

comment on function public.set_updated_at() is
  'Trigger function: stamps NEW.updated_at = now() on every UPDATE.';
