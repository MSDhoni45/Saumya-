-- =============================================================================
-- WhatsAgent AI — Migration 04: WhatsApp connection, contacts, conversations,
-- messages
-- =============================================================================

-- -----------------------------------------------------------------------------
-- whatsapp_connections: one connected WhatsApp Business number per org (MVP)
-- -----------------------------------------------------------------------------
create table public.whatsapp_connections (
  id                        uuid primary key default gen_random_uuid(),
  organization_id           uuid not null unique references public.organizations (id) on delete cascade,
  waba_id                   text,
  phone_number_id           text,
  display_phone_number      text,
  access_token_encrypted    bytea,
  webhook_verify_token      text,
  status                    public.connection_status not null default 'disconnected',
  connected_at              timestamptz,
  last_synced_at            timestamptz,
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);

create trigger trg_whatsapp_connections_updated_at
  before update on public.whatsapp_connections
  for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- contacts: a raw WhatsApp end-user the org has exchanged messages with
-- -----------------------------------------------------------------------------
create table public.contacts (
  id                    uuid primary key default gen_random_uuid(),
  organization_id       uuid not null references public.organizations (id) on delete cascade,
  whatsapp_phone        text not null,
  name                  text,
  email                 text,
  profile_attributes    jsonb not null default '{}'::jsonb,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  constraint contacts_org_phone_unique unique (organization_id, whatsapp_phone),
  constraint contacts_phone_format check (whatsapp_phone ~ '^\+[1-9][0-9]{6,14}$')
);

create index idx_contacts_org on public.contacts (organization_id);

create trigger trg_contacts_updated_at
  before update on public.contacts
  for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- conversations: a message thread between the org and a contact
-- -----------------------------------------------------------------------------
create table public.conversations (
  id                      uuid primary key default gen_random_uuid(),
  organization_id         uuid not null references public.organizations (id) on delete cascade,
  contact_id              uuid not null references public.contacts (id) on delete cascade,
  status                  public.conversation_status not null default 'open',
  ai_enabled              boolean not null default true,
  assigned_agent_type     public.agent_owner_type not null default 'ai',
  last_message_at         timestamptz,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);

create index idx_conversations_org on public.conversations (organization_id);
create index idx_conversations_org_status on public.conversations (organization_id, status);
create index idx_conversations_org_last_message on public.conversations (organization_id, last_message_at desc nulls last);
create index idx_conversations_contact on public.conversations (contact_id);

create trigger trg_conversations_updated_at
  before update on public.conversations
  for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- messages: individual inbound/outbound WhatsApp messages
-- -----------------------------------------------------------------------------
create table public.messages (
  id                      uuid primary key default gen_random_uuid(),
  conversation_id         uuid not null references public.conversations (id) on delete cascade,
  organization_id         uuid not null references public.organizations (id) on delete cascade,
  direction               public.message_direction not null,
  sender_type             public.message_sender_type not null,
  whatsapp_message_id     text,
  message_type            public.message_type not null default 'text',
  content                 text,
  media_url               text,
  status                  public.message_status not null default 'sent',
  ai_metadata             jsonb not null default '{}'::jsonb,
  created_at              timestamptz not null default now()
);

create index idx_messages_conversation_created on public.messages (conversation_id, created_at);
create index idx_messages_org_created on public.messages (organization_id, created_at desc);

-- Idempotency guard: Meta retries webhook deliveries, so the same
-- whatsapp_message_id must not be persisted twice per organization.
create unique index idx_messages_org_whatsapp_id_unique
  on public.messages (organization_id, whatsapp_message_id)
  where whatsapp_message_id is not null;

-- Keep conversations.last_message_at in sync for inbox sorting.
create or replace function public.touch_conversation_last_message_at()
returns trigger
language plpgsql
as $$
begin
  update public.conversations
     set last_message_at = new.created_at
   where id = new.conversation_id;
  return new;
end;
$$;

create trigger trg_messages_touch_conversation
  after insert on public.messages
  for each row execute function public.touch_conversation_last_message_at();
