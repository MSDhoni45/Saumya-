# WhatsAgent AI — System Design & Implementation Plan

This folder contains the complete planning artifacts for the WhatsAgent AI MVP:
a multi-tenant SaaS platform that lets businesses connect WhatsApp Business and
deploy configurable AI "employees" (sales agent, follow-up agent) backed by a
knowledge base, CRM, appointment booking, and analytics.

No application code is included in this set — these documents define **what**
to build and **how the pieces fit together** before implementation begins.

## Contents

1. [`01-system-architecture.md`](./01-system-architecture.md) — High-level
   architecture, components, data flows, multi-tenancy, security model.
2. [`02-database-schema.md`](./02-database-schema.md) — Full Supabase
   (Postgres + pgvector) schema: entities, fields, relationships, indexes, RLS.
3. [`03-api-architecture.md`](./03-api-architecture.md) — FastAPI REST API
   surface, conventions, auth model, background workers/jobs.
4. [`04-folder-structure.md`](./04-folder-structure.md) — Monorepo layout for
   the Next.js frontend and FastAPI backend.
5. [`05-roadmap-and-implementation-plan.md`](./05-roadmap-and-implementation-plan.md) —
   Phased roadmap with timeline estimates, task breakdowns, and acceptance
   criteria per phase.

## Tech stack (confirmed)

| Layer       | Choice                                              |
|-------------|-----------------------------------------------------|
| Frontend    | Next.js 15 (App Router), TypeScript, Tailwind, shadcn/ui |
| Backend     | FastAPI (Python)                                    |
| Database    | Supabase PostgreSQL (+ pgvector, Storage, Auth)     |
| AI          | OpenAI API + Anthropic Claude API (provider-agnostic orchestration layer) |
| Messaging   | Meta WhatsApp Cloud API                             |
| Calendar    | Google Calendar API (OAuth2)                        |
| Queue/Cache | Redis + Celery (background jobs, follow-up scheduler) |
| Frontend hosting | Vercel                                         |
| Backend hosting  | Container platform (Render / Fly.io / Railway / ECS) — FastAPI + workers run as long-lived services, which Vercel serverless functions are not suited for |

## How to read this set

Start with `01-system-architecture.md` for the big picture, then
`02-database-schema.md` to understand the data model, then
`03-api-architecture.md` for how the frontend/backend/integrations talk to each
other. `04-folder-structure.md` and `05-roadmap-and-implementation-plan.md`
turn the design into an actionable build plan.
