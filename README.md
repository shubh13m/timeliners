# Timeliner

Zero-cost AI news platform that turns Indian daily news into interactive chronological timelines.

- **Frontend:** Next.js 15 (PWA) on Cloudflare Pages
- **Database:** Supabase Postgres
- **Ingestion:** Python worker on GitHub Actions (3×/day IST)
- **AI:** Google Gemini 2.5 Flash-Lite
- **Push:** Web Push (VAPID)
- **Cost:** $0/month

See [PLAN.md](PLAN.md) for the full v1 implementation plan.

## Structure

```
timeliner/
├─ web/                 # Next.js frontend
├─ ingest/              # Python cron worker
├─ supabase/migrations/ # SQL migrations
├─ .github/workflows/   # GitHub Actions (cron, deploy, healthcheck)
└─ archive/             # Cold-storage JSON of archived stories
```

## Local dev

1. Copy `.env.local.example` → `.env.local` and fill in values.
2. See per-folder READMEs (`web/README.md`, `ingest/README.md`) for setup.

## License

MIT
