# 6. FastAPI Backend Architecture

This expands `01-system-architecture.md` and `04-folder-structure.md` into a
concrete backend design: how the FastAPI app is composed, how requests flow
through layers, and the conventions every module follows.

## 6.1 Layered architecture

```
Router (HTTP concerns: parsing, status codes, auth deps)
   │
   ▼
Service (business logic: orchestration, validation, side effects)
   │
   ▼
Repository / ORM models (data access via SQLAlchemy async session)
   │
   ▼
Postgres (Supabase) ── Redis (cache/queue) ── External APIs (WhatsApp, OpenAI, Claude, Google)
```

- **Routers** (`app/api/v1/*.py`) only translate HTTP ⇄ domain: validate input
  via Pydantic schemas, call a service, map the result/exception to a response.
  No business logic lives here.
- **Services** (`app/services/*`) hold orchestration logic — e.g.
  "qualify a lead from a conversation" touches `crm_service`, `ai/orchestrator`,
  and `follow_up_service`. Services are framework-agnostic (importable from
  Celery tasks too) and receive a DB session + resolved org context as
  arguments rather than reaching into request globals.
- **Models** (`app/models/*`) are SQLAlchemy 2.0 async ORM models that mirror
  `02-database-schema.md` 1:1. **Schemas** (`app/schemas/*`) are Pydantic
  v2 models for request/response validation — kept separate from ORM models so
  the API contract can evolve independently of storage.

## 6.2 Application factory & composition

`app/main.py` builds the app via a factory so tests can construct isolated
instances:

```
create_app(settings) ->
    FastAPI(
        title, version, lifespan=lifespan,   # startup/shutdown: DB engine, Redis pool
        dependencies=[Depends(request_context)],
    )
    .include_router(api_v1_router, prefix="/api/v1")
    .include_router(webhooks_router)          # no /api/v1 prefix, public
    + middleware stack
    + exception handlers
```

`lifespan` (async context manager) initializes/disposes the async SQLAlchemy
engine, Redis connection pool, and HTTP clients (OpenAI/Anthropic/WhatsApp/
Google) on startup/shutdown — avoiding per-request connection overhead.

## 6.3 Configuration

`app/core/config.py` uses `pydantic-settings` to load a typed `Settings`
object from environment variables (`.env` locally, platform secrets in
staging/prod). Settings are grouped by concern:

- `database_url`, `redis_url`
- `supabase_url`, `supabase_jwks_url`, `supabase_service_role_key`
- `openai_api_key`, `anthropic_api_key`
- `whatsapp_app_secret` (for webhook signature verification)
- `google_oauth_client_id` / `_client_secret` / `_redirect_uri`
- `token_encryption_key` (for encrypting WhatsApp/Google tokens at rest)
- `environment`, `log_level`, `cors_allowed_origins`

`get_settings()` is cached (`lru_cache`) and injected via `Depends` so tests
can override it.

## 6.4 Middleware stack (outermost → innermost)

1. **Request ID** — generates/propagates `X-Request-ID`, attaches to logs.
2. **CORS** — restricts to the configured frontend origin(s).
3. **Structured logging** — logs method, path, org_id, user_id, status, latency.
4. **Exception handling** — converts domain exceptions
   (`NotFoundError`, `PermissionDeniedError`, `ValidationError`,
   `ExternalServiceError`) into the standard `{ "error": {...} }` envelope with
   correct status codes; unhandled exceptions are logged with the request ID
   and returned as a generic `500`.
5. **Rate limiting** — per-IP on public endpoints (auth-adjacent, webhook),
   per-organization on expensive endpoints (AI test sandbox, exports).

## 6.5 Dependency injection chain (auth → org → role)

Every authenticated route composes from a small set of reusable dependencies,
each building on the previous and short-circuiting with the proper HTTP error:

```
get_db_session()                                  -> AsyncSession
get_current_user(Authorization header)            -> AuthenticatedUser (validates Supabase JWT via JWKS)
get_current_organization(X-Org-Id header, user)   -> OrganizationContext (verifies active membership)
require_role("admin" | "owner")                   -> raises 403 if the resolved membership lacks the role
```

Routers declare only what they need, e.g.:

```
@router.put("/agents/{agent_id}")
async def update_agent(
    agent_id: UUID,
    payload: AgentUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    org: OrganizationContext = Depends(require_role("admin")),
):
    return await agent_service.update(db, org, agent_id, payload)
```

This keeps authorization declarative and consistent — no hand-rolled checks
scattered through handler bodies.

## 6.6 Async I/O & external clients

- **Database**: SQLAlchemy 2.0 async engine + `asyncpg`, pooled per-process;
  one `AsyncSession` per request via dependency.
- **HTTP clients**: a shared `httpx.AsyncClient` per external service
  (WhatsApp Cloud API, OpenAI, Anthropic, Google), created at startup with
  sane timeouts/retries (via `tenacity` or `httpx` transport retries) and
  reused across requests/tasks.
- **Redis**: connection pool shared between the API process (caching, rate
  limiting) and Celery (broker/result backend).

## 6.7 Error model

A small exception hierarchy in `app/core/errors.py` maps 1:1 to HTTP statuses
via a registered exception handler:

| Exception | HTTP | Used for |
|---|---|---|
| `ValidationError` | 422 | domain-level validation beyond Pydantic |
| `NotFoundError` | 404 | missing resource within the org scope |
| `PermissionDeniedError` | 403 | role/ownership checks |
| `ConflictError` | 409 | duplicate resource (e.g. WhatsApp already connected) |
| `ExternalServiceError` | 502 | WhatsApp/OpenAI/Anthropic/Google failures |
| `RateLimitedError` | 429 | internal or upstream rate limits hit |

All map to `{ "error": { "code": "<snake_case>", "message": "...", "details": {...} } }`.

## 6.8 Background processing integration

FastAPI route handlers never call the LLM or WhatsApp APIs synchronously for
inbound-message processing — they enqueue a Celery task and return fast. The
same `services/*` modules are imported by both API routers (for synchronous
operations like "send a manual reply") and Celery tasks (for asynchronous
pipelines like "generate an AI reply"), so business logic is written once.

`app/workers/celery_app.py` configures Celery with Redis as broker/backend,
task routing (separate queues for `messages`, `ingestion`, `scheduled`,
`analytics` so a slow embeddings job can't starve message processing), and
`celery beat` schedules for periodic tasks (`run_follow_up_scheduler`,
`refresh_analytics_daily_stats`, `sync_calendar_events`).

## 6.9 Observability

- Structured JSON logs (request ID, org_id, user_id, route, latency, outcome).
- `ai_interactions` and webhook/audit tables double as an in-product
  observability layer (cost, latency, error tracking per organization).
- External error monitoring (e.g. Sentry) wired through the exception handler
  and Celery signal hooks.
- `/healthz` (liveness) and `/readyz` (DB + Redis connectivity) endpoints for
  the hosting platform's health checks.

## 6.10 Testing strategy

- **Unit tests**: services tested against a test database (or mocked session)
  with external clients replaced by fakes — fast, no network.
- **Integration tests**: routers tested via `httpx.AsyncClient` against the
  app factory with a real (containerized/test-schema) Postgres; auth
  dependencies overridden to inject a known user/org.
- **Contract tests**: fixtures of real WhatsApp webhook payloads (text, media,
  status updates, errors) validate the parsing/ingestion pipeline against
  Meta's documented schema, independent of live API availability.
- **Provider fakes**: `openai_provider`/`anthropic_provider` have
  test-double implementations so AI-dependent flows can be tested
  deterministically without burning API credits.
