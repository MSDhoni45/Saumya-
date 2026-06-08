-- conversations -------------------------------------------------------------
create table if not exists conversations (
  id                    uuid primary key default gen_random_uuid(),
  business_id           uuid not null references businesses (id) on delete cascade,
  whatsapp_account_id   uuid not null references whatsapp_accounts (id) on delete cascade,
  contact_phone         text not null,
  contact_name          text,
  status                text not null default 'open'
                          check (status in ('open', 'pending', 'handoff', 'closed')),
  assigned_user_id      uuid references users (id) on delete set null,
  last_message_at       timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists ix_conversations_business_id on conversations (business_id);
create index if not exists ix_conversations_whatsapp_account_id on conversations (whatsapp_account_id);
create index if not exists ix_conversations_assigned_user_id on conversations (assigned_user_id);
create index if not exists ix_conversations_business_status on conversations (business_id, status);
create unique index if not exists ux_conversations_account_contact
  on conversations (whatsapp_account_id, contact_phone);

create trigger trg_conversations_set_updated_at
  before update on conversations
  for each row execute function set_updated_at();

-- messages --------------------------------------------------------------------
create table if not exists messages (
  id                    uuid primary key default gen_random_uuid(),
  conversation_id       uuid not null references conversations (id) on delete cascade,
  business_id           uuid not null references businesses (id) on delete cascade,
  direction             text not null check (direction in ('inbound', 'outbound')),
  sender_type           text not null check (sender_type in ('contact', 'ai', 'agent', 'system')),
  message_type          text not null default 'text'
                          check (message_type in ('text', 'image', 'document', 'audio', 'video', 'template', 'location')),
  content               text,
  media_url             text,
  whatsapp_message_id   text,
  status                text not null default 'sent'
                          check (status in ('queued', 'sent', 'delivered', 'read', 'failed')),
  created_at            timestamptz not null default now()
);

create index if not exists ix_messages_conversation_created on messages (conversation_id, created_at);
create index if not exists ix_messages_business_id on messages (business_id);

-- Idempotency: never persist the same inbound WhatsApp webhook delivery twice.
create unique index if not exists ux_messages_whatsapp_message_id
  on messages (whatsapp_message_id) where whatsapp_message_id is not null;

-- Keep the parent conversation's `last_message_at` (and freshness ordering) in sync.
create or replace function touch_conversation_last_message_at()
returns trigger
language plpgsql
as $$
begin
  update conversations
     set last_message_at = new.created_at,
         updated_at      = now()
   where id = new.conversation_id;
  return new;
end;
$$;

create trigger trg_messages_touch_conversation
  after insert on messages
  for each row execute function touch_conversation_last_message_at();
