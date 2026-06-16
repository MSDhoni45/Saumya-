-- X (Twitter) Automation Module for Influnexus
-- Adds tables for connected X accounts, scheduled posts, lead search configs, and outreach tracking.

-- X accounts connected by businesses (OAuth 2.0 user tokens)
CREATE TABLE IF NOT EXISTS x_accounts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id     UUID        NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    x_user_id       TEXT        NOT NULL,
    username        TEXT        NOT NULL,
    display_name    TEXT,
    access_token    TEXT        NOT NULL,   -- Fernet-encrypted OAuth 2.0 user access token
    refresh_token   TEXT,                   -- Fernet-encrypted refresh token
    token_expires_at TIMESTAMPTZ,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(business_id, x_user_id)
);

CREATE INDEX IF NOT EXISTS ix_x_accounts_business_id ON x_accounts(business_id);

-- Scheduled and published tweets/threads
CREATE TABLE IF NOT EXISTS x_posts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id     UUID        NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    x_account_id    UUID        NOT NULL REFERENCES x_accounts(id) ON DELETE CASCADE,
    content         TEXT        NOT NULL,
    tweet_ids       TEXT[]      NOT NULL DEFAULT '{}',  -- IDs returned after posting (array for threads)
    thread_tweets   JSONB       NOT NULL DEFAULT '[]',  -- array of {text} objects for multi-tweet threads
    status          TEXT        NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','scheduled','posted','failed')),
    scheduled_at    TIMESTAMPTZ,
    posted_at       TIMESTAMPTZ,
    error_message   TEXT,
    engagement      JSONB       NOT NULL DEFAULT '{}',  -- {likes, retweets, replies, impressions}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_x_posts_business_id    ON x_posts(business_id);
CREATE INDEX IF NOT EXISTS ix_x_posts_status         ON x_posts(status);
CREATE INDEX IF NOT EXISTS ix_x_posts_scheduled_at   ON x_posts(scheduled_at) WHERE status = 'scheduled';

-- Lead search configurations (keywords to monitor on X)
CREATE TABLE IF NOT EXISTS x_lead_searches (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id         UUID        NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name                TEXT        NOT NULL,
    keywords            TEXT[]      NOT NULL,
    exclude_keywords    TEXT[]      NOT NULL DEFAULT '{}',
    min_followers       INT         NOT NULL DEFAULT 100,
    language            TEXT        NOT NULL DEFAULT 'en',
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    last_run_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_x_lead_searches_business_id ON x_lead_searches(business_id);

-- AI outreach tracking: X profiles found as potential leads
CREATE TABLE IF NOT EXISTS x_outreach (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id         UUID        NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    lead_id             UUID        REFERENCES leads(id) ON DELETE SET NULL,
    x_account_id        UUID        REFERENCES x_accounts(id) ON DELETE SET NULL,
    search_id           UUID        REFERENCES x_lead_searches(id) ON DELETE SET NULL,
    x_user_id           TEXT        NOT NULL,
    username            TEXT        NOT NULL,
    display_name        TEXT,
    profile_bio         TEXT,
    followers_count     INT,
    following_count     INT,
    tweet_text          TEXT,       -- the tweet that triggered discovery
    tweet_id            TEXT,
    ai_score            INT         CHECK (ai_score BETWEEN 0 AND 100),
    ai_score_reason     TEXT,       -- brief explanation from the LLM
    outreach_message    TEXT,       -- AI-generated reply/DM draft
    status              TEXT        NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','reviewed','sent','replied','converted','skipped')),
    sent_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(business_id, x_user_id, tweet_id)   -- no duplicate processing of same tweet
);

CREATE INDEX IF NOT EXISTS ix_x_outreach_business_id ON x_outreach(business_id);
CREATE INDEX IF NOT EXISTS ix_x_outreach_status      ON x_outreach(status);
CREATE INDEX IF NOT EXISTS ix_x_outreach_ai_score    ON x_outreach(ai_score DESC);

-- RLS: tenants only see their own rows
ALTER TABLE x_accounts      ENABLE ROW LEVEL SECURITY;
ALTER TABLE x_posts         ENABLE ROW LEVEL SECURITY;
ALTER TABLE x_lead_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE x_outreach      ENABLE ROW LEVEL SECURITY;
