-- knowledge_base ----------------------------------------------------------------
-- A named collection of source material (e.g. "Pricing", "FAQs") per business.
create table if not exists knowledge_base (
  id              uuid primary key default gen_random_uuid(),
  business_id     uuid not null references businesses (id) on delete cascade,
  name            text not null,
  description     text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index if not exists ix_knowledge_base_business_id on knowledge_base (business_id);

create trigger trg_knowledge_base_set_updated_at
  before update on knowledge_base
  for each row execute function set_updated_at();

-- documents -----------------------------------------------------------------------
-- One row per ingested chunk: keeps each embedding adjacent to the text it
-- represents so a similarity match returns directly retrievable content for RAG.
create table if not exists documents (
  id                  uuid primary key default gen_random_uuid(),
  knowledge_base_id   uuid not null references knowledge_base (id) on delete cascade,
  business_id         uuid not null references businesses (id) on delete cascade,
  title               text not null,
  source_type         text not null default 'text'
                        check (source_type in ('pdf', 'url', 'text', 'docx')),
  source_url          text,
  content             text not null,
  embedding           vector(1536),
  status              text not null default 'pending'
                        check (status in ('pending', 'processing', 'ready', 'failed')),
  error_message       text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index if not exists ix_documents_knowledge_base_id on documents (knowledge_base_id);
create index if not exists ix_documents_business_id on documents (business_id);
create index if not exists ix_documents_business_status on documents (business_id, status);

-- Cosine-distance ANN index for retrieval-augmented-generation lookups.
create index if not exists ix_documents_embedding_cosine
  on documents using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create trigger trg_documents_set_updated_at
  before update on documents
  for each row execute function set_updated_at();
