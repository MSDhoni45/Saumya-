-- ai_agents -----------------------------------------------------------------
-- One configurable "AI employee" per business (sales, support, follow-up...).
-- `qualification_fields` drives what the sales agent tries to capture from a
-- conversation, in priority order, e.g.
--   [{"key": "name", "label": "Full name", "required": true},
--    {"key": "budget", "label": "Budget range", "required": false}, ...]
create table if not exists ai_agents (
  id                      uuid primary key default gen_random_uuid(),
  business_id             uuid not null references businesses (id) on delete cascade,
  name                    text not null,
  agent_type              text not null default 'sales'
                            check (agent_type in ('sales', 'support', 'follow_up')),
  persona                 text not null default
    'You are a friendly, knowledgeable sales assistant. Be concise, helpful, and never invent facts about the business.',
  provider                text not null default 'openai'
                            check (provider in ('openai', 'anthropic')),
  model                   text not null default 'gpt-4o-mini',
  temperature             numeric(2,1) not null default 0.4 check (temperature >= 0 and temperature <= 2),
  qualification_fields    jsonb not null default '[]'::jsonb,
  is_active               boolean not null default true,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);

create index if not exists ix_ai_agents_business_id on ai_agents (business_id);
create index if not exists ix_ai_agents_business_type_active on ai_agents (business_id, agent_type, is_active);

create trigger trg_ai_agents_set_updated_at
  before update on ai_agents
  for each row execute function set_updated_at();

-- ai_interactions --------------------------------------------------------------
-- One row per agent turn: input/output, token usage, latency, and what (if
-- anything) was extracted from the exchange — powers AI-performance analytics
-- and gives a debuggable audit trail for "why did the agent say that?".
create table if not exists ai_interactions (
  id                      uuid primary key default gen_random_uuid(),
  business_id             uuid not null references businesses (id) on delete cascade,
  agent_id                uuid not null references ai_agents (id) on delete cascade,
  conversation_id         uuid not null references conversations (id) on delete cascade,
  inbound_message_id      uuid references messages (id) on delete set null,
  outbound_message_id     uuid references messages (id) on delete set null,
  provider                text not null,
  model                   text not null,
  prompt_tokens           integer,
  completion_tokens       integer,
  latency_ms              integer,
  retrieved_chunk_ids     uuid[] not null default '{}',
  extracted_lead_fields   jsonb not null default '{}'::jsonb,
  created_at              timestamptz not null default now()
);

create index if not exists ix_ai_interactions_business_id on ai_interactions (business_id);
create index if not exists ix_ai_interactions_conversation_id on ai_interactions (conversation_id, created_at);
create index if not exists ix_ai_interactions_agent_id on ai_interactions (agent_id);

-- leads: extend with the qualification fields the sales agent collects ---------
alter table leads
  add column if not exists budget text,
  add column if not exists service_interested text;

-- RLS ---------------------------------------------------------------------------
alter table ai_agents       enable row level security;
alter table ai_interactions enable row level security;

create policy ai_agents_select on ai_agents
  for select using (business_id = auth_business_id());

create policy ai_agents_write_admin on ai_agents
  for all
  using (business_id = auth_business_id() and auth_is_business_admin())
  with check (business_id = auth_business_id() and auth_is_business_admin());

create policy ai_interactions_select on ai_interactions
  for select using (business_id = auth_business_id());

create policy ai_interactions_insert on ai_interactions
  for insert with check (business_id = auth_business_id());
