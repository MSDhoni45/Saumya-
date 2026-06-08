-- =============================================================================
-- WhatsAgent AI — Migration 05: Knowledge base & vector embeddings (RAG)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- knowledge_base_documents: uploaded PDFs/DOCX or submitted website URLs
-- -----------------------------------------------------------------------------
create table public.knowledge_base_documents (
  id                uuid primary key default gen_random_uuid(),
  organization_id   uuid not null references public.organizations (id) on delete cascade,
  source_type       public.kb_source_type not null,
  title             text not null,
  storage_path      text,
  source_url        text,
  status            public.kb_document_status not null default 'pending',
  char_count        integer,
  chunk_count       integer,
  failure_reason    text,
  uploaded_by       uuid references public.profiles (id) on delete set null,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint kb_documents_source_payload_check check (
    (source_type in ('pdf', 'docx') and storage_path is not null)
    or (source_type = 'url' and source_url is not null)
  )
);

create index idx_kb_documents_org on public.knowledge_base_documents (organization_id);
create index idx_kb_documents_org_status on public.knowledge_base_documents (organization_id, status);

create trigger trg_kb_documents_updated_at
  before update on public.knowledge_base_documents
  for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- knowledge_base_chunks: chunked text + embeddings used for RAG retrieval
--
-- embedding dimension (1536) matches OpenAI text-embedding-3-small /
-- text-embedding-ada-002. If a different embedding model/dimension is chosen,
-- this column type must be updated accordingly (and the index rebuilt).
-- -----------------------------------------------------------------------------
create table public.knowledge_base_chunks (
  id                uuid primary key default gen_random_uuid(),
  document_id       uuid not null references public.knowledge_base_documents (id) on delete cascade,
  organization_id   uuid not null references public.organizations (id) on delete cascade,
  chunk_index       integer not null,
  content           text not null,
  embedding         vector(1536),
  token_count       integer,
  created_at        timestamptz not null default now(),
  constraint kb_chunks_document_index_unique unique (document_id, chunk_index)
);

create index idx_kb_chunks_org_document on public.knowledge_base_chunks (organization_id, document_id);

-- Approximate nearest-neighbour index for cosine-similarity search.
-- `lists` is a starting point for small/medium corpora; re-tune
-- (roughly sqrt(row_count)) as the table grows, per pgvector guidance.
create index idx_kb_chunks_embedding_cosine
  on public.knowledge_base_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);
