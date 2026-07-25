# Timelined — Complete Project Documentation

> **Purpose of this file:** A single, authoritative reference for the entire
> Timelined project so that any future Copilot / human contributor can pick up
> work in a new session without re-discovering context. If you (Copilot) are
> reading this at the start of a session, read the whole file before making
> changes.

---

## 1. Product

**Timelined** — Indian news aggregation that turns news into interactive
**chronological timelines**. Instead of showing "the latest headline", every
story is a growing list of dated events, so users can follow how a story
evolved over time.

- **Tagline:** *Follow the story, not just the headline.*
- **Live site:** https://timelined.pages.dev
- **Repo:** https://github.com/shubh13m/timeliners
- **Cost target:** **$0 / month** (all services on permanent free tiers).
- **Local root:** `C:\Users\pandeyshubha\timeliner`

---

## 2. High-level architecture

```
                     ┌────────────────────────────┐
                     │  GitHub Actions (cron)     │
                     │  6× / day, IST daytime     │
                     │  .github/workflows/*.yml   │
                     └──────────────┬─────────────┘
                                    │ runs
                                    ▼
                     ┌────────────────────────────┐
   RSS feeds ──────►│  ingest/  (Python 3.11)     │
   (Indian news)    │  fetch → normalize → dedup  │
                     │  → Gemini (extract events) │
                     │  → match / cluster        │
                     │  → persist                │
                     │  → push notify            │
                     └──────────────┬─────────────┘
                                    │ upsert
                                    ▼
                     ┌────────────────────────────┐
                     │  Supabase Postgres (Mumbai)│
                     │  stories, events, sources, │
                     │  push_subscriptions        │
                     └──────────────┬─────────────┘
                                    │ REST (anon key)
                                    ▼
                     ┌────────────────────────────┐
                     │  web/  Next.js 16 static    │
                     │  Cloudflare Pages CDN       │
                     │  PWA + Web Push             │
                     └────────────────────────────┘
                                    ▲
                                    │ pywebpush
                                    │ (VAPID)
                     ┌──────────────┴─────────────┐
                     │  Browsers / installed PWA  │
                     └────────────────────────────┘
```

**Data flow in one sentence:** Cron → Python ingester pulls RSS → Gemini
extracts structured events → matcher decides new-story vs append-to-existing
→ Supabase → static Next.js reads Supabase at build/runtime via REST → PWA
pushes users when new stories arrive.

---

## 3. Accounts, services, and how they are wired

| # | Service | Purpose | Tier | How it's linked |
|---|---------|---------|------|-----------------|
| 1 | **GitHub** (`shubh13m/timeliners`) | Source of truth, runs cron & deploys | Free | Repo secrets store all API tokens (see §4) |
| 2 | **Cloudflare Pages** | Static hosting + CDN for the Next.js `out/` bundle | Free | Deployed via `wrangler-action@v3` in `.github/workflows/deploy-web.yml`; project name `timelined` |
| 3 | **Supabase** (project in `ap-south-1` Mumbai) | Postgres DB + REST + auth-less anon reads | Free | Web uses anon key from public env; ingest uses **service role key** from GH secrets |
| 4 | **Google AI Studio / Gemini** | LLM: extract events + summaries from articles | Free (rate-limited) | `gemini-flash-lite-latest` via `google-generativeai` SDK, API key in GH secret `GEMINI_API_KEY` |
| 5 | **Web Push (VAPID)** | Browser push notifications | Free (self-hosted keys) | VAPID public key ships in web bundle; private key in GH secret `VAPID_PRIVATE_KEY`; server uses `pywebpush` |
| 6 | **RSS publishers** | News source of truth | Free public feeds | List lives in Supabase `sources` table; no API key needed |

**Nothing else has a paid tier.** No CDN egress cap has ever been approached.
No Supabase row/storage cap has been approached (85 stories, 135+ events).

---

## 4. Secrets & environment

### GitHub repo secrets (used by workflows)
| Secret name | Used by | What it is |
|---|---|---|
| `SUPABASE_URL` | ingest, deploy | `https://<ref>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | ingest | JWT for full DB write access — **never ship to browser** |
| `SUPABASE_ANON_KEY` | deploy (baked into web bundle) | Public read-only JWT |
| `GEMINI_API_KEY` | ingest | Google AI Studio key |
| `VAPID_PUBLIC_KEY` | deploy | Baked into web bundle (`NEXT_PUBLIC_VAPID_PUBLIC_KEY`) |
| `VAPID_PRIVATE_KEY` | ingest (push) | Signs Web Push envelopes |
| `VAPID_SUBJECT` | ingest (push) | `mailto:...` — VAPID requirement |
| `CLOUDFLARE_API_TOKEN` | deploy | Scoped to Pages:Edit on the `timelined` project |
| `CLOUDFLARE_ACCOUNT_ID` | deploy | Cloudflare account id |

### Local `.env.local` (never committed)
Same variables, plus optional `INGEST_DRY_RUN=1` for local testing. Template
lives in `.env.local.example`.

### Web-facing env (public, baked at build time — prefix `NEXT_PUBLIC_`)
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_VAPID_PUBLIC_KEY`

Anything else that gets referenced from the browser must be `NEXT_PUBLIC_*` or
the static build will not see it.

---

## 5. Repo layout

```
timeliner/
├─ web/                          Next.js 16 App Router, static export
│  ├─ app/
│  │  ├─ layout.tsx              Root layout: metadata, viewport, JSON-LD,
│  │  │                          PWA manifest link, boot-splash overlay
│  │  ├─ globals.css             Tailwind v4 + splash keyframes
│  │  ├─ page.tsx                Homepage — fetches stories on client
│  │  ├─ story/[slug]/page.tsx   Story detail — generateStaticParams
│  │  ├─ search/page.tsx         Client-side search (pg_trgm via RPC)
│  │  ├─ archive/page.tsx        Archived (inactive) stories list
│  │  └─ sitemap.ts              XML sitemap (is_active only)
│  ├─ components/
│  │  ├─ AppShell.tsx            Header (logo, search, Archive, Subscribe,
│  │  │                          tagline row), footer, SW registration
│  │  ├─ HomeClient.tsx          Homepage grid; sorts by latest_event_at DESC
│  │  ├─ StoryCard.tsx           Grid card; timeAgo(latest_event_at)
│  │  ├─ TimelinePanel.tsx       Event list; event_timestamp DESC + tiebreak
│  │  ├─ DateStepper.tsx         Compact prev/next date navigator
│  │  ├─ CategoryTabs.tsx        Category filter (a11y: aria-current)
│  │  └─ SubscribeButton.tsx     Web Push opt-in
│  ├─ lib/
│  │  ├─ supabase.ts             Anon client
│  │  └─ dates.ts                istDate / istToday / istDateAnchor
│  │                             — everything goes through Asia/Kolkata
│  ├─ public/
│  │  ├─ manifest.webmanifest    PWA manifest
│  │  ├─ sw.js                   Service worker (push handler)
│  │  └─ icons/                  PWA icons
│  ├─ next.config.ts             output:"export", trailingSlash:true
│  └─ package.json               Next 16.2.11, React 19.2.4, Tailwind v4
│
├─ ingest/                       Python 3.11 cron worker
│  ├─ main.py                    Orchestrator; called by ingest.yml
│  ├─ rss.py                     feedparser fetch + polite fetching
│  ├─ normalize.py               Clean HTML, resolve URLs
│  ├─ dedup.py                   URL + title-hash dedup
│  ├─ gemini.py                  Prompt + JSON extraction
│  ├─ schemas.py                 Pydantic models (Story, Event, ...)
│  ├─ matcher.py                 Decide: append to existing story vs new
│  ├─ cluster.py                 Group articles when creating a story
│  ├─ curator.py                 Titles / categories / tags
│  ├─ persist.py                 Supabase writes; collision-nudge on
│  │                             duplicate event_timestamp; refresh
│  │                             trending_score + last_updated
│  ├─ push.py                    notify_run_summary — ONE push per run
│  ├─ lifecycle.py               Mark stories inactive after N days idle
│  ├─ archive.py                 Cold-storage JSON dump
│  ├─ merge_stories.py           Manual admin script (dedupe stories)
│  ├─ backfill.py                One-off backfills
│  ├─ config.py                  Pydantic Settings from env
│  ├─ db.py                      supabase-py client
│  └─ requirements.txt
│
├─ supabase/migrations/
│  ├─ 0001_init.sql              Tables, indexes, extensions (pg_trgm, uuid-ossp)
│  └─ 0002_match_story.sql       RPC used by matcher for candidate lookup
│
├─ .github/workflows/
│  ├─ ingest.yml                 Cron 6×/day IST daytime + push notify
│  ├─ deploy-web.yml             Build web/, wrangler-action → Pages
│  ├─ archive.yml                Weekly archive of inactive stories
│  └─ healthcheck.yml            Ping homepage; alert on failure
│
├─ scripts/                      One-off Python helpers
├─ archive/                      Committed JSON archives (cold storage)
├─ PLAN.md                       Original v1 plan (kept for reference)
├─ README.md                     Short overview
└─ DOCS.md                       ← THIS FILE
```

---

## 6. Database schema (Supabase Postgres)

Migrations live in `supabase/migrations/`. Key tables:

### `stories`
- `id uuid pk`
- `slug text unique` — used in URLs `/story/<slug>/`
- `title text`
- `summary text`
- `category text` — one of a small enum (politics, tech, sport, ...)
- `tags text[]`
- `is_active bool` — inactive stories are hidden from homepage/sitemap
- `trending_score float` — decayed engagement heuristic
- `last_updated timestamptz` — set to `max(events.event_timestamp)` after each ingest
- `latest_event_at timestamptz` — same value, denormalized for sort
- `created_at timestamptz`

### `events`
- `id uuid pk`
- `story_id uuid fk → stories.id`
- `event_timestamp timestamptz` — the moment the event happened per Gemini
- `headline text`
- `body text`
- `source_url text`
- `source_name text`
- `created_at timestamptz`

**Sort convention everywhere:** `event_timestamp DESC, created_at DESC, id DESC`.
The multi-key tiebreak avoids UI flip-flop when two events share a timestamp.
Persist.py *also* nudges duplicate timestamps by ±seconds to make the ordering
deterministic in the DB itself.

### `sources`
List of RSS feed URLs with `name`, `homepage`, `is_active`, `weight`.

### `push_subscriptions`
- `endpoint text pk`
- `p256dh text`
- `auth text`
- `created_at timestamptz`

### RPCs
- `match_story(...)` — pg_trgm-based candidate lookup for matcher.py.
- (Optional) `search_stories(...)` — trigram search used by `/search`.

### Indexes
- pg_trgm on `stories.title` and `stories.summary`.
- `events (story_id, event_timestamp DESC)`.
- `stories (is_active, latest_event_at DESC)`.

---

## 7. Ingest pipeline (Python)

Entry point: `ingest/main.py`. Rough flow per run:

1. **Fetch** — `rss.py` polls every active source via feedparser.
2. **Normalize** — resolve redirects, strip trackers, extract publish time.
3. **Dedup** — skip URLs already seen (URL hash + title-hash cache).
4. **Extract with Gemini** — `gemini.py` sends article text and receives a
   JSON with title, summary, category, tags, and a list of `{event_timestamp,
   headline, body}` events. Schemas enforced by `schemas.py` (Pydantic).
5. **Match** — `matcher.py` calls the `match_story` RPC to find existing
   candidate stories via trigram similarity + shared entities. If a strong
   match, append events. Otherwise cluster.py starts a new story.
6. **Persist** — `persist.py` upserts stories and events, nudges duplicate
   timestamps, refreshes `trending_score`, sets `stories.last_updated` and
   `stories.latest_event_at` to `max(events.event_timestamp)`.
7. **Push notify** — `push.py::notify_run_summary(settings, new_story_count)`
   sends **one** generic notification per run (e.g. *"3 new stories
   timelined."*) — only when `new_story_count > 0`. This avoids spam.
8. **Lifecycle** — occasionally, stories idle for > N days are set
   `is_active=false`; archived via `archive.py` weekly.

**Return contract:** `process_articles(...)` returns
`tuple[int, int, int]` = `(new_story_count, appended_event_count,
skipped_count)`. All callers (including `backfill.py`) unpack three values.

---

## 8. Web app (Next.js)

- **Framework:** Next.js 16.2.11 App Router.
- **Rendering mode:** Static export (`output:"export"`, `trailingSlash:true`).
  There is **no Node server**. Every page is prerendered at build time; data
  that changes at runtime is fetched client-side from Supabase REST.
- **Styling:** Tailwind v4 (CSS-first, no `tailwind.config.js`; directives in
  `globals.css`).
- **PWA:** `public/manifest.webmanifest` + `public/sw.js`. Registered in
  `AppShell.tsx`. `viewport.themeColor = "#dc2626"`.
- **Boot splash:** Server-rendered `<div class="splash">` in `layout.tsx`
  with a pure-CSS fade animation (`.splash` in `globals.css`). Shows brand
  "Timelined" + tagline for ~1.2s, then fades over 0.6s. Respects
  `prefers-reduced-motion`. No JS required — visible on very first paint.
- **Time zone:** *All* date logic goes through `web/lib/dates.ts`. The IST
  helpers use `toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" })` so
  bucketing / DateStepper never drifts across midnight UTC.
- **Sort:** Homepage and StoryCard use `latest_event_at`, **not**
  `last_updated`. TimelinePanel uses
  `event_timestamp DESC → created_at DESC → id DESC`.
- **Error UX:** Homepage and search show a red banner if the Supabase fetch
  fails, instead of silently rendering an empty grid.
- **Search:** Client-side search hits a Supabase trigram RPC, then hydrates
  `event_count` and `latest_event_at` per result.
- **A11y:** CategoryTabs uses `aria-current="page"`, has a nav `aria-label`
  and a `focus-visible` ring.
- **Story detail edge case:** Zero-event stories render *"Timeline is being
  built. Check back after the next ingest run."* — they don't render an
  empty timeline.

---

## 9. Scheduling

All cron in GitHub Actions (`.github/workflows/*.yml`). GitHub cron is UTC.

| Workflow | Cron (UTC) | IST equivalent | Purpose |
|---|---|---|---|
| `ingest.yml` | `30 1,4,7,10,13,16 * * *` | 07, 10, 13, 16, 19, 22 IST | 6× daily ingest + push |
| `deploy-web.yml` | on push to `main` + `workflow_dispatch` | — | Rebuild + publish to Pages |
| `archive.yml` | weekly | — | Cold-storage archive of inactive stories |
| `healthcheck.yml` | hourly | — | HEAD request on homepage; open issue on failure |

Local scripts can be run any time; ingest is idempotent (URL dedup + upsert).

---

## 10. Fixes applied in recent sessions (context for future work)

This section captures the *why* of past changes so they aren't accidentally
undone.

1. **Timeline sort was flipping** — two events with identical
   `event_timestamp` swapped positions between renders. Fix:
   - `persist.py` nudges duplicate timestamps by ±seconds on insert.
   - `TimelinePanel.tsx` sorts by
     `event_timestamp DESC → created_at DESC → id DESC`.
   - Retroactively spread pre-existing duplicates via SQL.
2. **Date navigation** — replaced heavy horizontal DateCarousel with a
   compact prev/next `DateStepper`. Uses `istDateAnchor(date)` so it can't
   drift across timezones. When the requested date isn't in
   `availableDates`, falls back to nearest older (or newest if none).
3. **PWA had no theme color** — added
   `export const viewport: Viewport = { themeColor: "#dc2626", colorScheme: "dark" }`
   in `layout.tsx`.
4. **Cron only 3×/day** — bumped to 6× IST daytime
   (`30 1,4,7,10,13,16 * * *`).
5. **Homepage sort was wrong** — was using `last_updated`, which changed on
   any metadata edit. Switched to `latest_event_at` (real story recency) for
   both sort and StoryCard `timeAgo`.
6. **IST bucketing everywhere** — a single `web/lib/dates.ts` module; every
   date operation on the site goes through it.
7. **StoryCard truthfulness** — event count only rendered when
   `eventCount != null && eventCount > 0`, avoiding *"0 events"* stubs.
8. **Sitemap** — filtered by `is_active = true` so we don't list archived
   URLs.
9. **Push spam** — collapsed per-story pushes into **one summary push per
   ingest run** (`notify_run_summary`, gated on `new_story_count > 0`).
10. **Error banners** — homepage + search show a red banner on Supabase
    fetch failure instead of silent empty state.
11. **A11y** — CategoryTabs got `aria-current`, nav `aria-label`,
    `focus-visible` ring.
12. **Zero-event guard** — story detail page shows a message when a story
    has zero events.
13. **Persist cleanup** — removed a dead `res` query in `persist.py`.
14. **Backfill signature** — `backfill.py` unpacks the new 3-tuple
    `(new, appended, skipped)` returned by `process_articles`.
15. **Brand tagline** — *"Follow the story, not just the headline."* added
    to (a) header row and (b) boot splash overlay in `layout.tsx` +
    `globals.css`.

---

## 11. Conventions & gotchas

- **Never** commit `.env.local`.
- **Never** add code that reads Supabase with the service role key from the
  browser bundle. Anon key only in `NEXT_PUBLIC_*`.
- **Static export means no `app/api/*` routes at runtime.** If you need a
  server-side endpoint, put it in the ingester or a Supabase RPC.
- **Time zones:** always use `web/lib/dates.ts` on the frontend and
  timezone-aware `datetime` (or ISO strings ending in `Z`) in Python.
- **Sort order:** the canonical sort is defined in §6 (DB) and §8 (web).
  Don't invent a new one without updating both.
- **Push notifications:** ingest sends **one** summary push per run. Do not
  reintroduce per-story pushes without an explicit product decision.
- **Story detail is prerendered.** After ingest, Cloudflare Pages needs a
  redeploy for brand-new slugs to be reachable. Homepage/search/story data
  hydrates client-side, so *content* updates without redeploy — only new
  slugs need one. Redeploy is currently triggered on `push`; a
  workflow_dispatch step can be added if we want ingest to trigger a
  rebuild.
- **Duplicate event_timestamp:** always nudge on insert. Never rely on ORM
  ordering as a tiebreak.
- **Gemini output is untrusted.** Always validate through Pydantic
  (`schemas.py`) before touching the DB.
- **Rate limits.** Gemini free tier has per-minute and per-day caps. Ingest
  batches requests and backs off on 429.
- **Idempotency.** Ingest can be run any time; URL-hash dedup + upsert
  makes reruns safe.

---

## 12. How to run things

### Local dev — web
```powershell
cd C:\Users\pandeyshubha\timeliner\web
pnpm install
pnpm dev            # http://localhost:3000
pnpm build          # static export → web/out
```

### Local dev — ingest
```powershell
cd C:\Users\pandeyshubha\timeliner
.\.venv\Scripts\Activate.ps1
pip install -r ingest\requirements.txt
python -m ingest.main            # real run — writes to Supabase
$env:INGEST_DRY_RUN="1"; python -m ingest.main    # dry run
```

### Deploy
Just push to `main`. `deploy-web.yml` builds and publishes to Cloudflare
Pages. Ingest runs on its own cron; you don't have to trigger it.

### Ship a hotfix workflow
```powershell
cd C:\Users\pandeyshubha\timeliner
git add -A
git commit -m "fix(scope): short summary"
git push
```

---

## 13. Where to look when things break

| Symptom | First place to check |
|---|---|
| Homepage empty | Supabase → `stories` where `is_active=true`; then Actions → latest `ingest` run |
| Story detail 404 | New slug — needs a redeploy (`deploy-web.yml`) |
| Sort order flipping | `persist.py` timestamp-nudge, `TimelinePanel.tsx` tiebreak |
| Wrong date bucket at midnight IST | Anything not going through `web/lib/dates.ts` |
| Push not delivered | `push_subscriptions` row exists? VAPID subject set? `push.py` logs |
| Build fails on Pages | `pnpm build` locally first; check `NEXT_PUBLIC_*` secrets set in Actions |
| Gemini 429 | Free-tier rate limit — reduce cron frequency or article batch size |
| Healthcheck opened an issue | Cloudflare Pages incident, or the last deploy broke — roll back on GitHub |

---

## 14. Non-goals / explicit boundaries

- No user accounts, no comments, no likes. The product is read-only.
- No paid tiers. If a change requires paid infra, it must be discussed
  first.
- No SSR / edge functions. Static export only.
- No client-side heavy JS libraries. Keep the bundle small; the app must
  work on 3G Indian mobile.
- English only, India focus. Multi-language is out of scope for v1.

---

*Last updated: 2026-07-26. Update this file whenever you make a change that
future-you would need to know about before touching the codebase.*
