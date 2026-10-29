-- ImpactFund AI schema (PostgreSQL)
-- Apply with: psql "$DATABASE_URL" -f schema.sql

CREATE TABLE IF NOT EXISTS users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         VARCHAR(254) NOT NULL,
    display_name  VARCHAR(120) NOT NULL,
    role          VARCHAR(20) NOT NULL CHECK (role IN ('donor', 'organizer')),
    password_hash TEXT NOT NULL,
    profile_picture BYTEA,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS profile_picture BYTEA;

-- Emails are unique regardless of casing.
CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_idx ON users (LOWER(email));

CREATE TABLE IF NOT EXISTS campaigns (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title         VARCHAR(150) NOT NULL,
    description   TEXT NOT NULL,
    organiser     VARCHAR(100) NOT NULL,
    goal          NUMERIC NOT NULL CHECK (goal > 0),
    amount_raised NUMERIC NOT NULL DEFAULT 0 CHECK (amount_raised >= 0),
    status        VARCHAR(20) NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft', 'active', 'completed')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    owner_id      BIGINT REFERENCES users (id) ON DELETE SET NULL
);

-- Existing databases created before accounts existed need this column.
ALTER TABLE campaigns
    ADD COLUMN IF NOT EXISTS owner_id BIGINT REFERENCES users (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS campaigns_owner_id_idx ON campaigns (owner_id);
