"""Backfill historical news via Google News search RSS with date-range operators.

Google News RSS `/rss/search?q=...+after:YYYY-MM-DD+before:YYYY-MM-DD` returns
up to ~100 headlines within the specified window. We loop day-by-day and reuse
the normal ingest pipeline (cluster → match → dedup → events → persist).

Usage:
    python -m ingest.backfill --days 10
    python -m ingest.backfill --from 2026-07-01 --to 2026-07-15
    python -m ingest.backfill --days 5 --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import structlog

from . import lifecycle, rss
from .config import load_settings
from .gemini import CircuitBreakerOpen, GeminiClient
from .main import _setup_logging, process_articles
from .rss import Article

log = structlog.get_logger("backfill")

# One search query per broad topic. Each returns up to ~100 headlines per day.
# Keep the topic list tight to avoid burning quota; matches our 8 topic feeds.
BACKFILL_QUERIES: list[tuple[str, str]] = [
    ("India Top News", "india"),
    ("World", "world"),
    ("Business", "india business"),
    ("Technology", "india technology"),
    ("Sports", "india cricket OR sports"),
    ("Entertainment", "india entertainment OR bollywood"),
    ("Science", "india science"),
    ("Health", "india health"),
]

_GN_SEARCH = "https://news.google.com/rss/search"
_GN_SUFFIX = "hl=en-IN&gl=IN&ceid=IN:en"


def _build_sources_for_day(day: date) -> list[dict]:
    """Build ephemeral source dicts for a single day."""
    d_from = day.isoformat()
    d_to = (day + timedelta(days=1)).isoformat()
    sources: list[dict] = []
    for label, q in BACKFILL_QUERIES:
        url = (
            f"{_GN_SEARCH}?q={q.replace(' ', '+')}+after:{d_from}+before:{d_to}"
            f"&{_GN_SUFFIX}"
        )
        sources.append(
            {
                "name": f"backfill:{label}:{d_from}",
                "url": url,
                "credibility": "0.7",
            }
        )
    return sources


def _fetch_day(day: date, settings) -> list[Article]:
    """Fetch all backfill queries for a single day."""
    sources = _build_sources_for_day(day)
    all_articles: list[Article] = []
    for src in sources:
        articles = rss.fetch_source(src, settings)
        # Normalize each article's published_at into the requested day if the
        # feed returns odd times; keep original if it's already in-window.
        day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        for a in articles:
            if not (day_start <= a.published_at < day_end):
                # Coerce out-of-window timestamps (rare) to noon of the day
                # so clustering / event timestamps stay coherent.
                a_fixed = replace(
                    a,
                    published_at=day_start.replace(hour=12),
                )
                all_articles.append(a_fixed)
            else:
                all_articles.append(a)

    # Dedupe by URL across topic queries for this day.
    seen: set[str] = set()
    unique: list[Article] = []
    for a in all_articles:
        if a.url in seen:
            continue
        seen.add(a.url)
        unique.append(a)
    log.info("backfill_day_fetched", day=day.isoformat(), articles=len(unique))
    return unique


def run_backfill(start: date, end: date, dry_run: bool = False) -> int:
    settings = load_settings()
    log.info("backfill_start", start=start.isoformat(), end=end.isoformat(),
             days=(end - start).days + 1, dry_run=dry_run)

    gemini = GeminiClient(settings)

    total_stories = 0
    total_events = 0
    current = start
    day_count = 0

    while current <= end:
        day_count += 1
        log.info("backfill_day_start", day=current.isoformat(), n=day_count)
        try:
            articles = _fetch_day(current, settings)
        except Exception as e:
            log.error("backfill_fetch_failed", day=current.isoformat(), error=str(e))
            current += timedelta(days=1)
            continue

        if not articles:
            log.info("backfill_day_empty", day=current.isoformat())
            current += timedelta(days=1)
            continue

        try:
            s, e_ = process_articles(articles, settings, gemini, dry_run=dry_run)
            total_stories += s
            total_events += e_
            log.info(
                "backfill_day_complete",
                day=current.isoformat(),
                stories_updated=s,
                events_inserted=e_,
            )
        except CircuitBreakerOpen as e:
            log.error("circuit_breaker_open", day=current.isoformat(), error=str(e))
            break

        current += timedelta(days=1)
        # Gentle pacing between days — extra caution beyond gemini's own limiter.
        if current <= end:
            time.sleep(2)

    if not dry_run:
        lifecycle.sweep_inactive(settings)

    log.info(
        "backfill_complete",
        days=day_count,
        stories_updated=total_stories,
        events_inserted=total_events,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="timeliner-backfill")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--days", type=int, help="Number of days back from yesterday")
    grp.add_argument("--from", dest="date_from", type=str, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", type=str, help="YYYY-MM-DD (required with --from)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.days:
        end = date.today() - timedelta(days=1)  # yesterday (today is often incomplete)
        start = end - timedelta(days=args.days - 1)
    else:
        if not args.date_to:
            parser.error("--to is required with --from")
        start = date.fromisoformat(args.date_from)
        end = date.fromisoformat(args.date_to)
        if end < start:
            parser.error("--to must be >= --from")

    _setup_logging()
    logging.getLogger().setLevel(logging.INFO)
    try:
        return run_backfill(start, end, dry_run=args.dry_run)
    except Exception as e:
        log.exception("backfill_failed", error=str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
