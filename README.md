# Saumya

WhatsApp AI agent platform. FastAPI + Celery + Supabase + Meta WhatsApp Cloud API.

Inbound WhatsApp message → LLM (OpenAI / Anthropic) → reply sent via Graph API. RAG over uploaded knowledge base. Multi-tenant (business / agent / conversation). Operator alerts on send/status failures. Stripe + Razorpay billing.

## Stack

| Layer | Tech |
|-------|------|
| API | FastAPI, async SQLAlchemy + asyncpg |
| Worker | Celery + Redis |
| DB | Supabase Postgres (RLS) |
| Auth | Supabase GoTrue (JWT + httpOnly cookies) |
| LLM | OpenAI, Anthropic |
| Messaging | Meta WhatsApp Cloud API |
| Billing | Stripe, Razorpay |
| Deploy | Docker, AWS ECS (task defs in `infra/`) |

## Repo layout

```
apps/api/           FastAPI app, Celery workers
apps/web/           Frontend (separate deploy)
supabase/migrations/  SQL migrations (advisory-lock runner: app/db/migrate.py)
infra/              ECS task defs + deploy scripts
```

## Local setup

```bash
cd apps/api
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Required keys: DATABASE_URL, REDIS_URL, SUPABASE_*, OPENAI_API_KEY / ANTHROPIC_API_KEY,
#                WHATSAPP_APP_ID, WHATSAPP_APP_SECRET, WHATSAPP_WEBHOOK_VERIFY_TOKEN,
#                TOKEN_ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_hex(32))"

# migrations
python -m app.db.migrate

# api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# worker
celery -A app.workers.celery_app.celery_app worker --loglevel=info -Q celery

# beat
celery -A app.workers.celery_app.celery_app beat --loglevel=info
```

Public webhook (dev): `ngrok http 8000` → set Meta callback to `https://<ngrok>/webhooks/whatsapp`, verify token = `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, subscribe `messages` + `message_status`.

## API quickstart

```bash
API=http://localhost:8000/api/v1
JAR=/tmp/saumya.cookies

# signup creates user + business
curl -c $JAR -X POST $API/auth/signup -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"ChangeMe#2026","full_name":"You","business_name":"Acme"}'

# agent
curl -b $JAR -X POST $API/agents/<BIZ_ID> -H "Content-Type: application/json" \
  -d '{"name":"Saumya","agent_type":"sales","provider":"anthropic","model":"claude-sonnet-4-5","is_active":true}'

# connect WhatsApp
curl -b $JAR -X POST $API/whatsapp/<BIZ_ID>/connect -H "Content-Type: application/json" \
  -d '{"waba_id":"...","phone_number_id":"...","access_token":"<META_TOKEN>","display_name":"Acme"}'

# knowledge base + doc
curl -b $JAR -X POST $API/knowledge/<BIZ_ID> -d '{"name":"FAQ"}'
curl -b $JAR -X POST $API/knowledge/<BIZ_ID>/<KB_ID>/documents \
  -d '{"title":"Pricing","source_type":"text","content":"..."}'
```

## Tests

```bash
cd apps/api
pytest
```

## Deploy

ECS task defs in `infra/ecs/`. Deploy script `infra/scripts/deploy.sh`. Requires: VPC, ALB, ACM cert, Secrets Manager `whatsagent/prod`, IAM roles `whatsagent-ecs-execution-role` + `whatsagent-ecs-task-role`, ECS cluster `whatsagent-prod` with services `api` / `worker` / `beat`.

## Contributing

PRs welcome. Fork, branch, PR against `main`.

## License

MIT — see [LICENSE](LICENSE).
