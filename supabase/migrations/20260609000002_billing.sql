-- ---------------------------------------------------------------------------
-- Billing: subscriptions, usage tracking, and audit log
-- ---------------------------------------------------------------------------

-- subscriptions: one row per business, tracks plan + provider IDs.
CREATE TABLE IF NOT EXISTS subscriptions (
    id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id              UUID        NOT NULL UNIQUE REFERENCES businesses(id) ON DELETE CASCADE,
    plan                     VARCHAR(50) NOT NULL DEFAULT 'free',
    status                   VARCHAR(50) NOT NULL DEFAULT 'active',   -- active | trialing | past_due | cancelled | paused
    payment_provider         VARCHAR(50),                             -- stripe | razorpay | NULL (free)

    -- Stripe
    stripe_customer_id       VARCHAR(255) UNIQUE,
    stripe_subscription_id   VARCHAR(255) UNIQUE,

    -- Razorpay
    razorpay_customer_id     VARCHAR(255),
    razorpay_subscription_id VARCHAR(255) UNIQUE,

    current_period_start     TIMESTAMPTZ,
    current_period_end       TIMESTAMPTZ,
    cancel_at_period_end     BOOLEAN     NOT NULL DEFAULT FALSE,
    trial_ends_at            TIMESTAMPTZ,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX subscriptions_business_idx ON subscriptions (business_id);

-- Back-fill: give every existing business a free subscription so the
-- get_or_create_subscription helper never has to INSERT during a hot path.
INSERT INTO subscriptions (business_id, plan, status)
SELECT id, 'free', 'active'
FROM businesses
ON CONFLICT (business_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- usage_records: one row per (business × billing month).
-- The UNIQUE constraint enables the ON CONFLICT upsert in increment_usage().
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usage_records (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id    UUID        NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    period_start   TIMESTAMPTZ NOT NULL,
    period_end     TIMESTAMPTZ NOT NULL,
    message_count  INTEGER     NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (business_id, period_start)
);

CREATE INDEX usage_records_business_idx ON usage_records (business_id);

-- ---------------------------------------------------------------------------
-- billing_events: immutable append-only audit log.
-- provider_event_id is the idempotency key — duplicate webhook deliveries
-- are detected and silently skipped by the application layer.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS billing_events (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id       UUID        NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    event_type        VARCHAR(100) NOT NULL,
    provider          VARCHAR(50),
    provider_event_id VARCHAR(255) UNIQUE,
    payload           JSONB       NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX billing_events_business_idx ON billing_events (business_id);
