-- =============================================================
-- Timeliner v1 — Story fuzzy matcher RPC
-- Run this in Supabase SQL Editor after 0001_init.sql.
-- =============================================================

CREATE OR REPLACE FUNCTION match_story(
    q TEXT,
    threshold REAL DEFAULT 0.4,
    only_active BOOLEAN DEFAULT TRUE
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    is_active BOOLEAN,
    similarity REAL
) LANGUAGE sql STABLE AS $$
    SELECT s.id, s.title, s.is_active,
           similarity(s.title, q)::real AS similarity
    FROM stories s
    WHERE (NOT only_active OR s.is_active = TRUE)
      AND similarity(s.title, q) >= threshold
    ORDER BY similarity DESC, s.last_updated DESC
    LIMIT 1;
$$;
