"""Idempotent DB writes for stories, timeline events, and daily digests."""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime, timezone

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
) -> str:
    """Create or update a story. Returns the story_id."""
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()
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

    new_id = deterministic_story_id(title, today)
    slug = make_slug(title, today)
    payload = {
        "id": new_id,
        "title": title[:500],
        "slug": slug,
        "category": category or "India Top News",
        "summary": summary,
        "is_active": True,
        "first_seen_at": now,
        "last_updated": now,
    }
    # ON CONFLICT DO NOTHING via upsert with ignore_duplicates.
    client.table("stories").upsert(payload, on_conflict="id", ignore_duplicates=True).execute()
    log.info("story_created", story_id=new_id, title=title[:80])
    return new_id


def insert_events(story_id: str, events: list[EventOut], articles: list[Article]) -> int:
    """Insert new events idempotently. Returns count inserted."""
    if not events:
        return 0
    client = get_client()
    rows = []
    for ev in events:
        source_url = ""
        source_name = ""
        content_hash = ""
        if 0 <= ev.source_index < len(articles):
            a = articles[ev.source_index]
            source_url = a.url
            source_name = a.source
            content_hash = a.content_hash
        else:
            content_hash = hashlib.sha256(
                f"{story_id}|{ev.event_timestamp.isoformat()}|{ev.headline}".encode()
            ).hexdigest()
        rows.append(
            {
                "story_id": story_id,
                "event_timestamp": ev.event_timestamp.isoformat(),
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
