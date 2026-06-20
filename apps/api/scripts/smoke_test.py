"""End-to-end smoke test against a running API (staging or local).

Runs the friendly-customer pilot path: signup → me → plans → agent create →
agent test → whatsapp accounts (empty) → logout. Exits non-zero on first
failure so it can gate a deploy or CI step.

Usage:
    BASE_URL=https://api.staging.whatsagent.ai python -m scripts.smoke_test
    # or against local:
    BASE_URL=http://localhost:8000 python -m scripts.smoke_test
"""

from __future__ import annotations

import os
import sys
import time
import uuid

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = float(os.environ.get("SMOKE_TIMEOUT", "15"))


def _fail(step: str, response: httpx.Response | None, extra: str = "") -> None:
    body = ""
    if response is not None:
        body = response.text[:500]
        print(f"FAIL {step}: HTTP {response.status_code} {body}")
    else:
        print(f"FAIL {step}: {extra}")
    sys.exit(1)


def _ok(step: str, detail: str = "") -> None:
    print(f"OK   {step}{(' — ' + detail) if detail else ''}")


def main() -> None:
    suffix = uuid.uuid4().hex[:10]
    email = f"smoke+{suffix}@whatsagent.test"
    password = f"SmokeTest!{suffix}"
    start = time.time()

    print(f"BASE_URL={BASE_URL}")
    print(f"email={email}")
    print("---")

    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
        # 1. health
        r = client.get("/health")
        if r.status_code != 200:
            _fail("health", r)
        _ok("health")

        # 2. signup (creates business)
        r = client.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "password": password,
                "full_name": "Smoke Test",
                "business_name": f"Smoke Biz {suffix}",
            },
        )
        if r.status_code != 201:
            _fail("signup", r)
        session = r.json()
        access_token = session["access_token"]
        business_id = session["user"].get("business_id")
        if not business_id:
            _fail("signup", None, "no business_id on user")
        _ok("signup", f"business_id={business_id}")

        headers = {"Authorization": f"Bearer {access_token}"}

        # 3. /auth/me
        r = client.get("/api/v1/auth/me", headers=headers)
        if r.status_code != 200:
            _fail("auth/me", r)
        me = r.json()
        if me["user"]["email"] != email:
            _fail("auth/me", None, "email mismatch")
        _ok("auth/me")

        # 4. billing plans
        r = client.get(f"/api/v1/billing/{business_id}/plans", headers=headers)
        if r.status_code != 200:
            _fail("billing/plans", r)
        plans = r.json()
        if not isinstance(plans, list) or not plans:
            _fail("billing/plans", None, "no plans returned")
        _ok("billing/plans", f"{len(plans)} plan(s)")

        # 5. billing subscription (may 404 pre-checkout; accept 200 or 404)
        r = client.get(f"/api/v1/billing/{business_id}/subscription", headers=headers)
        if r.status_code not in (200, 404):
            _fail("billing/subscription", r)
        _ok("billing/subscription", f"status={r.status_code}")

        # 6. agents list (expect empty)
        r = client.get(f"/api/v1/agents/{business_id}", headers=headers)
        if r.status_code != 200:
            _fail("agents/list", r)
        if r.json():
            _fail("agents/list", None, "expected empty list on fresh business")
        _ok("agents/list", "empty")

        # 7. create agent
        r = client.post(
            f"/api/v1/agents/{business_id}",
            headers=headers,
            json={
                "name": "Smoke Sales Bot",
                "agent_type": "sales",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.4,
                "qualification_fields": [
                    {"key": "budget", "label": "Budget range", "required": False}
                ],
                "is_active": True,
            },
        )
        if r.status_code != 201:
            _fail("agents/create", r)
        agent_id = r.json()["id"]
        _ok("agents/create", f"agent_id={agent_id}")

        # 8. agent sandbox test (skip if LLM key not wired — accept 200 or 502)
        r = client.post(
            f"/api/v1/agents/{business_id}/{agent_id}/test",
            headers=headers,
            json={"message": "Hi, what are your prices?", "history": [], "known_lead_fields": {}},
        )
        if r.status_code not in (200, 502, 503):
            _fail("agents/test", r)
        _ok("agents/test", f"status={r.status_code}")

        # 9. whatsapp accounts list (expect empty)
        r = client.get(f"/api/v1/whatsapp/{business_id}/accounts", headers=headers)
        if r.status_code != 200:
            _fail("whatsapp/accounts", r)
        if r.json():
            _fail("whatsapp/accounts", None, "expected empty list on fresh business")
        _ok("whatsapp/accounts", "empty")

        # 10. logout
        r = client.post("/api/v1/auth/logout", headers=headers)
        if r.status_code != 200:
            _fail("auth/logout", r)
        _ok("auth/logout")

    elapsed = time.time() - start
    print("---")
    print(f"PASS — all checks green in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
