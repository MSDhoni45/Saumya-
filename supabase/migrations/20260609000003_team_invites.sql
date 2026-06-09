-- ---------------------------------------------------------------------------
-- Team invites: allow business admins to invite people by email
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS team_invites (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id     UUID         NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    invited_by_id   UUID         REFERENCES users(id) ON DELETE SET NULL,
    email           VARCHAR(255) NOT NULL,
    role            VARCHAR(50)  NOT NULL DEFAULT 'team_member',
    token           VARCHAR(255) NOT NULL UNIQUE,
    -- pending | accepted | revoked
    status          VARCHAR(50)  NOT NULL DEFAULT 'pending',
    expires_at      TIMESTAMPTZ  NOT NULL,
    accepted_by_id  UUID         REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX team_invites_business_idx ON team_invites (business_id);
CREATE INDEX team_invites_token_idx    ON team_invites (token);
-- Quickly check for an existing pending invite for an email+business pair.
CREATE INDEX team_invites_email_business_idx ON team_invites (lower(email), business_id);
