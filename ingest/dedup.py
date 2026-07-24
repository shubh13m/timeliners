"""Content-hash deduplication filter."""
from __future__ import annotations

import structlog

from .db import get_client
from .rss import Article

log = structlog.get_logger(__name__)


def existing_hashes(story_id: str) -> set[str]:
    if not story_id:
        return set()
    res = (
        get_client()
        .table("timeline_events")
        .select("content_hash")
        .eq("story_id", story_id)
        .execute()
    )
    return {r["content_hash"] for r in (res.data or [])}


def filter_new(articles: list[Article], seen: set[str]) -> list[Article]:
    return [a for a in articles if a.content_hash not in seen]


def existing_timeline(story_id: str) -> list[dict]:
    if not story_id:
        return []
    res = (
        get_client()
        .table("timeline_events")
        .select("event_timestamp,headline,details,event_type")
        .eq("story_id", story_id)
        .order("event_timestamp", desc=False)
        .limit(50)
        .execute()
    )
    return res.data or []
