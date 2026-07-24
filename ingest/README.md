# Timeliner Ingest Worker

Python 3.11+ pipeline that fetches RSS, clusters via Gemini, updates timelines in Supabase, and sends push notifications.

## Local setup (Windows PowerShell)

```powershell
cd ingest
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Fill in `.env.local` at the repo root (see `.env.local.example`).

## Run

```powershell
# From repo root:
python -m ingest.main --dry-run   # no DB writes
python -m ingest.main             # full run
```

## Modules

| File | Purpose |
|---|---|
| `main.py` | Orchestrator (Phases 1–8) |
| `config.py` | Env vars, constants, RSS sources |
| `rss.py` | Feed fetching with ETag caching |
| `cluster.py` | Cheap keyword clustering + Gemini refinement |
| `matcher.py` | pg_trgm fuzzy match to existing stories |
| `dedup.py` | Content-hash filter, existing timeline lookup |
| `gemini.py` | Gemini client + retry / circuit breaker / rate limit / audit log |
| `schemas.py` | Pydantic validation of Gemini output |
| `persist.py` | Idempotent DB writes |
| `lifecycle.py` | Mark stories inactive after N days |
| `push.py` | Web Push (VAPID) dispatch |
| `archive.py` | Monthly cold archive to `archive/YYYY-MM.json` |
| `db.py` | Supabase client factory |

## Optional: Postgres RPC for faster matching

For faster story matching, create this RPC in Supabase (SQL Editor). Without it, the worker falls back to `ILIKE`.

```sql
CREATE OR REPLACE FUNCTION match_story(q TEXT, only_active BOOLEAN, threshold REAL)
RETURNS TABLE (id UUID, title TEXT, is_active BOOLEAN, sim REAL)
LANGUAGE sql STABLE AS $$
    SELECT s.id, s.title, s.is_active, similarity(s.title, q) AS sim
    FROM stories s
    WHERE (NOT only_active OR s.is_active)
      AND similarity(s.title, q) > threshold
    ORDER BY sim DESC
    LIMIT 1;
$$;
```
