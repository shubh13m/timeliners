-- =============================================================
-- Timeliner v1 — Initial schema
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- =============================================================

-- ---------- Extensions ----------
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------- Tables ----------

-- 1. Stories (overarching news topics)
CREATE TABLE IF NOT EXISTS stories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    slug            TEXT NOT NULL UNIQUE,
    category        TEXT NOT NULL DEFAULT 'India Top News',
    summary         TEXT,
    trending_score  REAL NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_tsv      TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(summary, '')), 'B')
    ) STORED
);

-- 2. Timeline events (chronological milestones per story)
CREATE TABLE IF NOT EXISTS timeline_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id          UUID NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    event_timestamp   TIMESTAMPTZ NOT NULL,
    headline          TEXT NOT NULL,
    details           TEXT,
    source_url        TEXT,
    source_name       TEXT,
    content_hash      TEXT NOT NULL,
    event_type        TEXT NOT NULL DEFAULT 'update'
                      CHECK (event_type IN ('announcement','verdict','statement','update','correction')),
    confidence        REAL NOT NULL DEFAULT 1.0,
    parent_event_id   UUID REFERENCES timeline_events(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (story_id, content_hash)
);

-- 3. Daily digest index (which stories appeared on which day)
CREATE TABLE IF NOT EXISTS daily_digests (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    digest_date      DATE NOT NULL,
    story_id         UUID NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    summary_snippet  TEXT,
    display_order    INT NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (digest_date, story_id)
);

-- 4. Push subscriptions (Web Push VAPID)
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    endpoint       TEXT NOT NULL UNIQUE,
    p256dh         TEXT NOT NULL,
    auth           TEXT NOT NULL,
    story_filter   JSONB NOT NULL DEFAULT '{}'::jsonb,
    user_agent     TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. AI runs audit log
CREATE TABLE IF NOT EXISTS ai_runs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    phase             TEXT NOT NULL,
    prompt_hash       TEXT,
    prompt_tokens     INT,
    response_tokens   INT,
    response          JSONB,
    status            TEXT NOT NULL,
    error             TEXT
);

-- ---------- Indexes ----------
CREATE INDEX IF NOT EXISTS idx_stories_active_updated
    ON stories (is_active, last_updated DESC);

CREATE INDEX IF NOT EXISTS idx_stories_category_active
    ON stories (category, is_active, last_updated DESC);

CREATE INDEX IF NOT EXISTS idx_stories_title_trgm
    ON stories USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_stories_search_tsv
    ON stories USING gin (search_tsv);

CREATE INDEX IF NOT EXISTS idx_timeline_story_ts
    ON timeline_events (story_id, event_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_digests_date
    ON daily_digests (digest_date DESC, display_order);

CREATE INDEX IF NOT EXISTS idx_ai_runs_time
    ON ai_runs (run_at DESC);

-- ---------- Full-text search RPC ----------
CREATE OR REPLACE FUNCTION search_stories(q TEXT, lim INT DEFAULT 20)
RETURNS TABLE (
    id UUID,
    title TEXT,
    slug TEXT,
    category TEXT,
    summary TEXT,
    last_updated TIMESTAMPTZ,
    rank REAL
) LANGUAGE sql STABLE AS $$
    SELECT s.id, s.title, s.slug, s.category, s.summary, s.last_updated,
           ts_rank(s.search_tsv, plainto_tsquery('english', q)) AS rank
    FROM stories s
    WHERE s.search_tsv @@ plainto_tsquery('english', q)
    ORDER BY rank DESC, s.last_updated DESC
    LIMIT lim;
$$;

-- ---------- Row Level Security ----------
ALTER TABLE stories             ENABLE ROW LEVEL SECURITY;
ALTER TABLE timeline_events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_digests       ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_subscriptions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_runs             ENABLE ROW LEVEL SECURITY;

-- Public read: stories / events / digests
DROP POLICY IF EXISTS "public read stories"        ON stories;
DROP POLICY IF EXISTS "public read events"         ON timeline_events;
DROP POLICY IF EXISTS "public read digests"        ON daily_digests;

CREATE POLICY "public read stories"
    ON stories FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "public read events"
    ON timeline_events FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "public read digests"
    ON daily_digests FOR SELECT
    TO anon, authenticated
    USING (true);

-- Push subscriptions: anyone can insert their own; nobody can read/update/delete via anon
DROP POLICY IF EXISTS "anon insert subscription" ON push_subscriptions;
CREATE POLICY "anon insert subscription"
    ON push_subscriptions FOR INSERT
    TO anon, authenticated
    WITH CHECK (true);

-- ai_runs: no anon access at all (service role bypasses RLS)
-- (No policy created → default deny.)
