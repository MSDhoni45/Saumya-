# 4. Folder Structure

Monorepo containing the Next.js frontend, FastAPI backend, shared docs, and
deployment infra.

```
/
├── apps/
│   ├── web/                        # Next.js 15 frontend
│   └── api/                        # FastAPI backend
├── docs/
│   └── architecture/               # this design/planning set
├── infra/                          # deployment configs, docker-compose for local dev
└── README.md
```

## 4.1 Frontend — `apps/web/` (Next.js 15, App Router, TS, Tailwind, shadcn/ui)

```
apps/web/
├── app/
│   ├── (marketing)/                # public landing/pricing pages
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   ├── signup/page.tsx
│   │   └── reset-password/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx              # authenticated shell: sidebar, topbar, org switcher
│   │   ├── dashboard/page.tsx      # KPI overview
│   │   ├── inbox/                  # conversations / live chat view
│   │   ├── knowledge-base/         # document & URL management
│   │   ├── agents/                 # AI agent persona/config
│   │   ├── crm/                    # leads pipeline (kanban + detail)
│   │   ├── appointments/           # calendar/list view
│   │   ├── follow-ups/             # sequence builder
│   │   ├── analytics/              # charts & exports
│   │   └── settings/
│   │       ├── organization/
│   │       ├── whatsapp/
│   │       ├── team/
│   │       └── billing/
│   ├── api/                        # Next.js route handlers (OAuth redirects, light proxying)
│   └── layout.tsx
├── components/
│   ├── ui/                         # shadcn primitives
│   ├── dashboard/
│   ├── inbox/
│   ├── crm/
│   └── shared/
├── lib/
│   ├── supabase/                   # browser/server Supabase client helpers
│   ├── api/                        # typed FastAPI client + react-query hooks
│   ├── hooks/
│   └── utils/
├── stores/                         # client-side state (e.g., zustand) where needed
├── types/                          # shared TS types (mirrors backend Pydantic schemas)
├── styles/
├── middleware.ts                   # session/auth middleware, org-context resolution
└── public/
```

## 4.2 Backend — `apps/api/` (FastAPI)

```
apps/api/
├── app/
│   ├── main.py                     # app factory, router registration, middleware
│   ├── core/
│   │   ├── config.py               # pydantic-settings (env-driven config)
│   │   ├── security.py             # JWT validation, org-context dependencies
│   │   └── logging.py
│   ├── api/
│   │   └── v1/
│   │       ├── router.py
│   │       ├── auth.py
│   │       ├── dashboard.py
│   │       ├── whatsapp.py
│   │       ├── conversations.py
│   │       ├── knowledge_base.py
│   │       ├── agents.py
│   │       ├── leads.py
│   │       ├── appointments.py
│   │       ├── follow_ups.py
│   │       └── analytics.py
│   ├── webhooks/
│   │   └── whatsapp.py             # public webhook receiver (signature verification)
│   ├── models/                     # ORM models (SQLAlchemy/SQLModel) mirroring the schema
│   ├── schemas/                    # Pydantic request/response models
│   ├── services/
│   │   ├── whatsapp_client.py      # Cloud API wrapper (send, media, templates)
│   │   ├── ai/
│   │   │   ├── orchestrator.py     # provider-agnostic LLM interface
│   │   │   ├── openai_provider.py
│   │   │   ├── anthropic_provider.py
│   │   │   ├── rag.py              # retrieval pipeline (pgvector similarity search)
│   │   │   └── prompts/            # persona/system prompt templates
│   │   ├── knowledge_base/
│   │   │   ├── extractors.py       # PDF / DOCX / URL text extraction
│   │   │   └── chunking.py         # text splitting + embedding orchestration
│   │   ├── crm_service.py          # lead lifecycle, stage transitions, activities
│   │   ├── calendar_service.py     # Google OAuth + availability + event creation
│   │   └── follow_up_service.py    # enrollment rules, step progression
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── tasks/
│   │       ├── inbound_messages.py
│   │       ├── knowledge_base.py
│   │       ├── follow_ups.py
│   │       └── analytics.py
│   ├── db/
│   │   ├── session.py              # async SQLAlchemy session/engine
│   │   └── base.py
│   └── utils/
├── migrations/                     # Alembic migrations (source of truth for schema)
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml / requirements.txt
└── Dockerfile
```

## 4.3 Infra — `infra/`

```
infra/
├── docker-compose.yml              # local dev: postgres+pgvector, redis, api, worker
├── Dockerfile.worker
└── env/
    ├── .env.example                # documents required env vars per service
    └── README.md
```

## 4.4 Notes on shared types

To keep the Next.js frontend and FastAPI backend in sync, generate TypeScript
types from the FastAPI OpenAPI schema (e.g., `openapi-typescript`) into
`apps/web/types/api/` as part of the build/dev pipeline — avoids hand-written,
drifting duplicate type definitions.
