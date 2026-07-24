# Timeliner v1 — Step-by-Step Implementation Plan

## Locked scope for v1 (everything approved, nothing more)

**Stack**
- Frontend: Next.js 15 (App Router) + TypeScript + Tailwind, PWA-enabled
- Hosting: Cloudflare Pages (`timeliner.pages.dev`)
- DB: Supabase Postgres (with RLS, `pg_trgm`, `tsvector`)
- Cron: Python 3.11 on GitHub Actions, 3×/day IST (07:00, 14:00, 22:00)
- AI: Gemini 2.5 Flash-Lite, JSON mode, batched (~6 calls/day)
- Push: Web Push + VAPID (`pywebpush`), no FCM
- RSS: Google News India + PIB + PTI

**Features (all in v1)**
- Auto ingestion + clustering + dedup + timeline update for existing stories
- 10 tracked stories/day, 14-day inactivity lifecycle (feed-hide only, still browsable)
- Shift-left UI (100% feed → 35% feed + 65% timeline)
- Bottom historical date carousel + daily digests
- Full-text search (`tsvector` + GIN)
- Category filters (Politics/Sports/Business/etc.)
- Web push subscriptions + notifications on new events
- Deep-linkable `/story/[id]`, dynamic OG images
- Offline PWA (service worker + IndexedDB cache of last 3 days)
- Sitemap.xml + RSS output of our timelines
- Structured data (`NewsArticle` JSON-LD)
- MVP hardening: retry, circuit breaker, rate-limit guard, idempotent inserts, deterministic IDs, `ai_runs` audit table, confidence scoring
- Cold-archive job to repo, monthly retention
- Health-check + GitHub Actions failure email

---

## Phase 0 — Accounts & prerequisites (day 0, ~30 min)

**0.1** Install locally (Windows): Node 20 LTS, Python 3.11, Git, VS Code. Verify `node -v`, `python --version`.
**0.2** Create accounts (all free): GitHub, Supabase, Google AI Studio, Cloudflare.
**0.3** In Google AI Studio → generate a Gemini API key.
**0.4** In Supabase → create project `timeliner` (region: Mumbai/Singapore). Copy `URL`, `anon key`, `service_role key`.
**0.5** Generate VAPID keypair: `npx web-push generate-vapid-keys`. Save both keys.
**0.6** Create empty GitHub repo `timeliner` (public — free unlimited Actions).

**Deliverable:** `.env.local.example` file listing all env var names (no secrets committed).

---

## Phase 1 — Repository skeleton (day 1, ~1 hour)

**1.1** Init monorepo structure:
```
timeliner/
├─ web/                 # Next.js frontend
├─ ingest/              # Python cron worker
├─ supabase/
│   └─ migrations/      # SQL files, numbered
├─ .github/workflows/   # Actions YAML
├─ archive/             # cold storage JSON dumps
├─ .env.local.example
├─ .gitignore
├─ README.md
└─ LICENSE (MIT)
```
**1.2** Root `.gitignore` covers `.env*`, `node_modules`, `__pycache__`, `.venv`, `.next`, `dist`.
**1.3** Commit initial skeleton.

**Deliverable:** Empty but structured repo pushed to GitHub.

---

## Phase 2 — Supabase schema & security (day 1, ~2 hours)

**2.1** Enable extensions: `pg_trgm`, `pgcrypto`, `uuid-ossp`.
**2.2** Create tables (migration `0001_init.sql`):
- `stories` (id, title, slug, category, summary, last_updated, is_active, created_at, trending_score)
- `timeline_events` (id, story_id FK, event_timestamp, headline, details, source_url, content_hash UNIQUE-per-story, event_type, confidence, created_at)
- `daily_digests` (id, digest_date, story_id FK, summary_snippet, display_order)
- `push_subscriptions` (id, endpoint UNIQUE, p256dh, auth, story_filter jsonb, created_at)
- `ai_runs` (id, run_at, phase, prompt_hash, prompt_tokens, response_tokens, response jsonb, status, error)
- `search_index` — generated `tsvector` column on `stories` + GIN index

**2.3** Indexes: `(story_id, event_timestamp DESC)`, `(digest_date)`, `(is_active, last_updated DESC)`, `pg_trgm` GIN on `stories.title`.
**2.4** RLS policies:
- Anon: `SELECT` on `stories`, `timeline_events`, `daily_digests` only
- Anon: `INSERT` on `push_subscriptions` (rate-limited via unique endpoint)
- Service role: full access (used by cron)
**2.5** Deterministic slug function: `slugify(title) || '-' || substr(md5(title||first_seen_date), 1, 6)`.
**2.6** Deploy via Supabase CLI: `supabase db push`.

**Deliverable:** Live schema in Supabase, verified with `SELECT * FROM stories LIMIT 1`.

---

## Phase 3 — Python ingestion worker (days 2–4, ~1 day of work)

Module layout in `ingest/`:
```
ingest/
├─ main.py              # entry point, orchestrates phases
├─ config.py            # env vars, constants
├─ rss.py               # feed fetching + parsing
├─ cluster.py           # Phase 2 Gemini clustering + cheap keyword pre-cluster
├─ matcher.py           # DB fuzzy-match existing stories
├─ dedup.py             # content_hash filter
├─ gemini.py            # Gemini client, retry, circuit breaker, rate limit
├─ persist.py           # idempotent DB writes
├─ lifecycle.py         # 14-day inactivity sweep + auto-revive
├─ push.py              # web push dispatch via pywebpush
├─ archive.py           # monthly cold archive
├─ schemas.py           # Pydantic models for Gemini output validation
├─ requirements.txt
└─ tests/
```

**3.1** `rss.py`: fetch Google News India, PIB, PTI with ETag/Last-Modified caching (state in `ingest/.cache/`). Returns normalized `Article(title, url, published_at, source, snippet)`.

**3.2** `cluster.py`:
- Cheap first pass: TF-IDF keyword grouping in-Python (`sklearn` optional or DIY).
- Ambiguous groups → Gemini clustering call (Phase 2 🤖 CALL #1).
- Output: 10 clusters with `{title, category, article_indices, confidence}`. Drop confidence < 0.6.

**3.3** `matcher.py`: for each cluster, `SELECT id, title FROM stories WHERE is_active=true AND similarity(title, :t) > 0.4 ORDER BY similarity DESC LIMIT 1`. Also check inactive stories for auto-revive.

**3.4** `dedup.py`: `content_hash = sha256(source_url)`. `SELECT content_hash FROM timeline_events WHERE story_id=X`. Filter out already-seen articles. If cluster fully deduplicated → skip Gemini entirely.

**3.5** `gemini.py`:
- Wrapper around `google-generativeai` with `response_mime_type='application/json'`.
- Retry once on invalid JSON with stricter prompt.
- Circuit breaker: 3 consecutive failures → abort run.
- Rate-limit guard: min 5s between calls (well under 15 req/min).
- Log every call to `ai_runs` table.

**3.6** Phase 5 batched call (🤖 CALL #2): one prompt with array of `{cluster, existing_timeline}`, returns array of `{new_events, updated_summary}`. Validate with Pydantic.

**3.7** `persist.py`:
- Deterministic IDs: `uuid5(NAMESPACE, normalized_title + first_seen_date)` for stories.
- `INSERT ... ON CONFLICT DO NOTHING` on `timeline_events(story_id, content_hash)`.
- `UPDATE stories SET last_updated=NOW(), summary=..., is_active=true` on match.
- Refresh `trending_score = event_count_last_24h * source_diversity`.
- Insert/update `daily_digests` for today.

**3.8** `lifecycle.py`: `UPDATE stories SET is_active=false WHERE last_updated < NOW() - INTERVAL '14 days'`.

**3.9** `push.py`: for each story with new events, fetch matching subscriptions (respect `story_filter`), send via `pywebpush`. Delete `410 Gone` subscriptions.

**3.10** `archive.py` (runs 1st of month): export stories inactive >90 days to `archive/YYYY-MM.json` in repo, `git commit + push`, then `DELETE` from DB.

**3.11** `main.py`: sequential runner with structured logging (`structlog`), exits non-zero on failure.

**3.12** Tests: unit-test each module with mocked Gemini/Supabase (`pytest`).

**Deliverable:** `python -m ingest.main --dry-run` works locally against a test Supabase project.

---

## Phase 4 — GitHub Actions workflows (day 5, ~2 hours)

**4.1** `.github/workflows/ingest.yml`:
- Cron: `30 1,8,16 * * *` (01:30, 08:30, 16:30 UTC = 07:00, 14:00, 22:00 IST)
- Steps: checkout → setup-python → pip install → run `python -m ingest.main` → upload logs artifact
- Secrets: `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_SUBJECT`
- On failure: send email via built-in Actions notification (already free).

**4.2** `.github/workflows/archive.yml`: monthly cron `0 0 1 * *`, runs `python -m ingest.archive`, commits archive folder back.

**4.3** `.github/workflows/healthcheck.yml`: every 6 hours, pings Supabase REST + Cloudflare Pages URL, opens an issue on failure.

**4.4** `.github/workflows/deploy-web.yml`: on push to `main` affecting `web/**`, build Next.js and deploy to Cloudflare Pages via `wrangler`.

**Deliverable:** All 4 workflows visible in Actions tab, ingest runs green on manual trigger.

---

## Phase 5 — Next.js frontend scaffolding (days 6–7)

**5.1** `cd web && npx create-next-app@latest . --ts --tailwind --app --no-src-dir`. Add `next-pwa`.
**5.2** Folder plan:
```
web/app/
├─ layout.tsx           # global shell, service worker registration
├─ page.tsx             # homepage: feed + shift-left timeline
├─ story/[slug]/page.tsx
├─ archive/page.tsx
├─ search/page.tsx
├─ api/
│   ├─ subscribe/route.ts    # POST push subscription → Supabase
│   ├─ og/[slug]/route.tsx   # dynamic OG image (edge runtime)
│   └─ rss/route.ts          # our own RSS output
├─ sitemap.ts
└─ robots.ts
web/components/
├─ Feed.tsx
├─ StoryCard.tsx
├─ TimelinePanel.tsx
├─ DateCarousel.tsx
├─ CategoryTabs.tsx
├─ SearchBar.tsx
├─ SubscribeButton.tsx
└─ ShiftLeftShell.tsx      # controls the 100%↔35%/65% layout state
web/lib/
├─ supabase.ts           # anon client
├─ pwa.ts                # service worker helpers
├─ push.ts               # subscribe flow, VAPID handshake
├─ idb.ts                # IndexedDB cache for offline
└─ types.ts
```

**5.3** Data fetching: use Next.js `fetch` with `revalidate: 300` (ISR) for CDN caching. All queries go through anon client + RLS.

**5.4** Homepage renders top active stories filtered by selected category, sorted by `trending_score`. Reader-time chip per card.

**5.5** `ShiftLeftShell` uses CSS grid transitions:
- Default: `grid-template-columns: 1fr 0`
- Selected: `grid-template-columns: 35% 65%` on ≥768px, full-screen slide on mobile
- Framer Motion for the transition.

**5.6** `TimelinePanel`: vertical connected milestones, event-type icons, "corrected on" links, source badges (weighted by credibility).

**5.7** `DateCarousel`: horizontal scroll of last 30 days; tap → route to `/?date=YYYY-MM-DD` → loads `daily_digests`.

**5.8** `SearchBar`: hits Supabase RPC `search_stories(q)` using `tsvector`.

**5.9** `SubscribeButton`: prompts push permission, POSTs subscription to `/api/subscribe` with optional `story_filter`.

**5.10** Offline: service worker precaches shell + last 3 days of stories to IndexedDB on visit. Fallback page for offline.

**5.11** SEO: `sitemap.ts` lists all active stories, `robots.ts` allows all, JSON-LD `NewsArticle` on story page, `/api/rss` outputs our timelines as RSS.

**5.12** Dynamic OG image via `next/og` at edge.

**Deliverable:** `pnpm dev` shows homepage with real Supabase data, shift-left works, PWA installable.

---

## Phase 6 — Backfill & first end-to-end run (day 8)

**6.1** Run `python -m ingest.main --backfill --days 7` locally against production Supabase → seeds ~70 stories.
**6.2** Manually trigger `ingest.yml` from Actions UI → verify 6 Gemini calls, new events inserted.
**6.3** Deploy `web/` to Cloudflare Pages. Verify `timeliner.pages.dev` loads.
**6.4** Test push: subscribe on phone → trigger ingest → verify notification arrives.
**6.5** Test offline: airplane mode → homepage still loads from IndexedDB.

**Deliverable:** Public live URL with real data, cron scheduled, push working.

---

## Phase 7 — Hardening & QA (day 9)

**7.1** Force-fail Gemini calls → verify circuit breaker + email alert.
**7.2** Re-run cron twice back-to-back → verify idempotency (no duplicate events).
**7.3** Load test: hit homepage 100× → verify CDN cache hit ratio > 90% (Cloudflare analytics).
**7.4** Lighthouse: PWA ≥90, Performance ≥90, SEO ≥95.
**7.5** RLS test: try to `INSERT` into `stories` with anon key → must fail.
**7.6** Search test: search "election" → returns expected stories in <200ms.
**7.7** Category filter, date carousel, archive page, RSS output, sitemap all validated.

**Deliverable:** Signed-off QA checklist committed to repo.

---

## Phase 8 — Documentation & launch (day 10)

**8.1** `README.md`: architecture diagram, local dev setup, env var list, how to add an RSS source, how to run tests.
**8.2** `docs/runbook.md`: what to do if Supabase pauses, if Gemini quota hits, if Actions fails.
**8.3** Tag `v1.0.0`, publish GitHub release.

**Deliverable:** v1 live at `https://timeliner.pages.dev`.

---

## Free-tier budget after v1

| Resource | Consumed | Free limit | Headroom |
|---|---|---|---|
| GitHub Actions | ~50 min/mo | Unlimited (public repo) | ∞ |
| Gemini calls | ~6/day + retries | 1,500/day | 99% |
| Supabase DB size | ~5 MB/yr (with archive) | 500 MB | 99% |
| Supabase bandwidth | ~1 GB/mo | 5 GB | 80% |
| Cloudflare Pages | Static | Unlimited BW | ∞ |
| Web Push | Free protocol | Unlimited | ∞ |

**Total monthly cost: $0.**

---

## Timeline

~10 working days of focused work (or 2–3 weeks calendar).
