-- Canonicalize documents.status: legacy `'error'` rows -> `'failed'`.
--
-- The CHECK constraint on `documents.status` (see migration
-- 20260608130006_knowledge_base_and_documents.sql) already enforces the
-- canonical set ('pending', 'processing', 'ready', 'failed'). A worker bug
-- (knowledge_tasks._embed_document) was attempting to write 'error', which
-- would have been rejected by the CHECK and never persisted — but this
-- migration is defensive: if any environment ever bypassed the constraint
-- (e.g. constraint disabled during a maintenance window), reconcile here.
--
-- Idempotent: no-op when zero legacy rows exist. Constraint is intentionally
-- NOT recreated — it is already correct.

update documents
   set status = 'failed'
 where status = 'error';
