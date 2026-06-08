create table if not exists whatsapp_accounts (
  id                uuid primary key default gen_random_uuid(),
  business_id       uuid not null references businesses (id) on delete cascade,
  display_name      text,
  phone_number      text not null,
  waba_id           text not null,
  phone_number_id   text not null,
  access_token      text,                    -- encrypted at the application layer before storage
  status            text not null default 'pending'
                      check (status in ('pending', 'connected', 'disconnected', 'error')),
  connected_at      timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index if not exists ix_whatsapp_accounts_business_id on whatsapp_accounts (business_id);
create unique index if not exists ux_whatsapp_accounts_phone_number_id on whatsapp_accounts (phone_number_id);

create trigger trg_whatsapp_accounts_set_updated_at
  before update on whatsapp_accounts
  for each row execute function set_updated_at();
