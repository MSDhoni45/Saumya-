-- document_chunks ----------------------------------------------------------------
-- One row per token-bounded slice of a `documents.content` body. RAG retrieval
-- queries this table directly so similarity search returns the exact passage
-- the model should ground on, instead of the whole document (which previously
-- forced a 30 000-char truncation and collapsed long-form sources into a
-- single embedding vector — P0 retrieval bug).
--
-- `documents.embedding` is kept on the parent row for backward compatibility
-- with code paths that have not yet migrated; new retrieval reads from here.

create table if not exists document_chunks (
  id                uuid primary key default gen_random_uuid(),
  document_id       uuid not null references documents (id) on delete cascade,
  business_id       uuid not null references businesses (id) on delete cascade,
  chunk_index       integer not null,
  content           text not null,
  embedding         vector(1536),
  token_count       integer,
  created_at        timestamptz not null default now(),
  constraint document_chunks_document_index_unique unique (document_id, chunk_index)
);

create index if not exists ix_document_chunks_document_id on document_chunks (document_id);
create index if not exists ix_document_chunks_business_id on document_chunks (business_id);

-- Cosine-distance ANN index for retrieval-augmented-generation lookups.
create index if not exists ix_document_chunks_embedding_cosine
  on document_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- RLS — mirror `documents` exactly: business-scoped read, admin-only write.
alter table document_chunks enable row level security;

create policy document_chunks_select on document_chunks
  for select using (business_id = auth_business_id());

create policy document_chunks_write_admin on document_chunks
  for all
  using (business_id = auth_business_id() and auth_is_business_admin())
  with check (business_id = auth_business_id() and auth_is_business_admin());

-- Backfill -----------------------------------------------------------------------
-- Existing `documents` rows in status='ready' already hold a single embedding
-- vector representing the (truncated) full content. Seed one chunk per such
-- document so live RAG queries against the new table return at least the
-- pre-migration behaviour until the worker re-embeds the document properly.
insert into document_chunks (document_id, business_id, chunk_index, content, embedding)
select id, business_id, 0, content, embedding
  from documents
 where status = 'ready'
   and embedding is not null
on conflict on constraint document_chunks_document_index_unique do nothing;
