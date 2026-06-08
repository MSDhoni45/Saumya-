-- =============================================================================
-- WhatsAgent AI — Migration 06: AI agents & interaction logs
-- =============================================================================

-- -----------------------------------------------------------------------------
-- ai_agents: configurable "AI employees" (sales, follow-up, support) per org
-- -----------------------------------------------------------------------------
create table public.ai_agents (
  id                      uuid primary key default gen_random_uuid(),
  organization_id         uuid not null references public.organizations (id) on delete cascade,
  type                    public.ai_agent_type not null,
  name                    text not null,
  persona_prompt          text not null default '',
  model_provider          public.model_provider not null default 'openai',
  model_name              text not null default 'gpt-4.1',
  temperature             numeric(3, 2) not null default 0.70,
  qualification_fields    jsonb not null default '["name", "phone", "email", "budget", "location"]'::jsonb,
  is_active               boolean not null default true,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now(),
  constraint ai_agents_org_type_unique unique (organization_id, type),
  constraint ai_agents_temperature_range check (temperature >= 0 and temperature <= 2)
);

create index idx_ai_agents_org on public.ai_agents (organization_id);

create trigger trg_ai_agents_updated_at
  before update on public.ai_agents
  for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- ai_interactions: observability/cost log for every LLM call
-- -----------------------------------------------------------------------------
create table public.ai_interactions (
  id                      uuid primary key default gen_random_uuid(),
  organization_id         uuid not null references public.organizations (id) on delete cascade,
  conversation_id         uuid references public.conversations (id) on delete set null,
  agent_id                uuid references public.ai_agents (id) on delete set null,
  provider                public.model_provider not null,
  model_name              text not null,
  prompt_tokens           integer not null default 0,
  completion_tokens       integer not null default 0,
  total_cost_usd          numeric(12, 6) not null default 0,
  latency_ms              integer,
  request_prompt          jsonb,
  response_text           text,
  created_at              timestamptz not null default now()
);

create index idx_ai_interactions_org_created on public.ai_interactions (organization_id, created_at desc);
create index idx_ai_interactions_conversation on public.ai_interactions (conversation_id);
create index idx_ai_interactions_agent on public.ai_interactions (agent_id);
