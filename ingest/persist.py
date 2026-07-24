"""Idempotent DB writes for stories, timeline events, and daily digests."""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import structlog

from .db import get_client
from .rss import Article
from .schemas import EventOut

log = structlog.get_logger(__name__)

_NAMESPACE = uuid.UUID("6b3f2b30-1a2e-4b91-9c66-8f7c1a4b5d10")


def _slugify(title: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return s[:60] or "story"


def deterministic_story_id(title: str, first_seen: date) -> str:
    key = f"{_slugify(title)}|{first_seen.isoformat()}"
    return str(uuid.uuid5(_NAMESPACE, key))


def make_slug(title: str, first_seen: date) -> str:
    suffix = hashlib.md5(f"{title}|{first_seen.isoformat()}".encode()).hexdigest()[:6]
    return f"{_slugify(title)}-{suffix}"


def upsert_story(
    story_id: str | None,
    title: str,
    category: str,
    summary: str,
    was_inactive: bool = False,
    first_seen_ts: datetime | None = None,
) -> str:
    """Create or update a story. Returns the story_id.

    ``first_seen_ts`` is used for new stories only. Pass the earliest article
    (or event) timestamp so backfilled historical stories are anchored to the
    date they actually broke instead of the ingest wall-clock.
    """
    client = get_client()
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    today = date.today()

    if story_id:
        payload = {
            "last_updated": now,
            "is_active": True,
        }
        if summary:
            payload["summary"] = summary
        client.table("stories").update(payload).eq("id", story_id).execute()
        if was_inactive:
            log.info("story_revived", story_id=story_id, title=title[:80])
        return story_id

    seed_ts = first_seen_ts or now_dt
    seed_iso = seed_ts.isoformat()
    seed_day = seed_ts.date()

    new_id = deterministic_story_id(title, seed_day)
    slug = make_slug(title, seed_day)
    payload = {
        "id": new_id,
        "title": title[:500],
        "slug": slug,
        "category": category or "India Top News",
        "summary": summary,
        "is_active": True,
        "first_seen_at": seed_iso,
        "last_updated": now,
    }
    # ON CONFLICT DO NOTHING via upsert with ignore_duplicates.
    client.table("stories").upsert(payload, on_conflict="id", ignore_duplicates=True).execute()
    log.info("story_created", story_id=new_id, title=title[:80])
    return new_id


def insert_events(story_id: str, events: list[EventOut], articles: list[Article]) -> int:
    """Insert new events idempotently. Returns count inserted.

    Clamps each event's ``event_timestamp`` into the min/max ``published_at``
    range of the cluster articles (with a 12-hour cushion on each side) to
    prevent Gemini from hallucinating ``today`` when the sources are historical.
    Falls back to the matched source article's timestamp when available,
    otherwise the cluster median.
    """
    if not events:
        return 0
    client = get_client()

    # Build the article publish-time envelope for this cluster.
    pub_times = sorted(a.published_at for a in articles if a.published_at)
    if pub_times:
        lo = pub_times[0] - timedelta(hours=12)
        hi = pub_times[-1] + timedelta(hours=12)
        median = pub_times[len(pub_times) // 2]
    else:
        lo = hi = median = datetime.now(timezone.utc)

    rows = []
    for ev in events:
        source_url = ""
        source_name = ""
        content_hash = ""
        source_pub: datetime | None = None
        if 0 <= ev.source_index < len(articles):
            a = articles[ev.source_index]
            source_url = a.url
            source_name = a.source
            content_hash = a.content_hash
            source_pub = a.published_at
        else:
            content_hash = hashlib.sha256(
                f"{story_id}|{ev.event_timestamp.isoformat()}|{ev.headline}".encode()
            ).hexdigest()

        ts = ev.event_timestamp
        # Ensure timezone-aware for comparison.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if not (lo <= ts <= hi):
            snapped = source_pub or median
            log.info(
                "event_timestamp_clamped",
                story_id=story_id,
                original=ts.isoformat(),
                snapped_to=snapped.isoformat(),
                headline=ev.headline[:60],
            )
            ts = snapped

        rows.append(
            {
                "story_id": story_id,
                "event_timestamp": ts.isoformat(),
                "headline": ev.headline,
                "details": ev.details or "",
                "source_url": source_url,
                "source_name": source_name,
                "content_hash": content_hash,
                "event_type": ev.event_type,
                "confidence": ev.confidence,
            }
        )
    # Upsert with ignore_duplicates on (story_id, content_hash) unique constraint.
    client.table("timeline_events").upsert(
        rows, on_conflict="story_id,content_hash", ignore_duplicates=True
    ).execute()
    log.info("events_inserted", story_id=story_id, count=len(rows))
    return len(rows)


def upsert_daily_digest(
    story_id: str, snippet: str, display_order: int, when: date | None = None
) -> None:
    when = when or date.today()
    client = get_client()
    client.table("daily_digests").upsert(
        {
            "digest_date": when.isoformat(),
            "story_id": story_id,
            "summary_snippet": (snippet or "")[:500],
            "display_order": display_order,
        },
        on_conflict="digest_date,story_id",
    ).execute()


def refresh_trending_score(story_id: str) -> None:
    """trending_score = events_last_24h * distinct_sources_last_24h."""
    client = get_client()
    # Fetch recent events; compute in Python (avoids RPC dependency).
    res = (
        client.table("timeline_events")
        .select("source_name,created_at")
        .eq("story_id", story_id)
        .gte(
            "created_at",
            (datetime.now(timezone.utc).replace(microsecond=0)).isoformat(),
        )
        .execute()
    )
    # Simpler: count last-24h events by created_at using order + limit.
    res2 = (
        client.table("timeline_events")
        .select("source_name,created_at")
        .eq("story_id", story_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    now = datetime.now(timezone.utc)
    recent = []
    for row in res2.data or []:
        try:
            ts = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        if (now - ts).total_seconds() <= 86400:
            recent.append(row)
    count = len(recent)
    sources = len({r.get("source_name") or "" for r in recent if r.get("source_name")})
    score = float(count * max(sources, 1))
    client.table("stories").update({"trending_score": score}).eq("id", story_id).execute()
