"""Match clusters to existing DB stories using pg_trgm similarity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog

from .config import STORY_SIMILARITY_THRESHOLD
from .db import get_client

log = structlog.get_logger(__name__)


@dataclass
class Match:
    story_id: str
    title: str
    similarity: float
    was_inactive: bool


def _query_similar(title: str, only_active: bool) -> Optional[Match]:
    """Find the most similar existing story via pg_trgm.
    Uses the pg REST endpoint through supabase-py's rpc.
    We use raw SQL via the postgrest 'similarity' filter isn't available directly,
    so we fetch candidate rows by ilike and score in Python as a fallback,
    or we call an RPC. Simplest: use RPC.
    """
    client = get_client()
    try:
        rpc_name = "match_story"
        res = client.rpc(
            rpc_name,
            {"q": title, "only_active": only_active,
             "threshold": STORY_SIMILARITY_THRESHOLD},
        ).execute()
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]
        return Match(
            story_id=row["id"],
            title=row["title"],
            similarity=float(row.get("sim", 0.0)),
            was_inactive=not row.get("is_active", True),
        )
    except Exception as e:
        # RPC may not exist; fall back to a simple ilike search.
        log.debug("match_rpc_missing_fallback", error=str(e))
        return _fallback_ilike(title, only_active)


def _fallback_ilike(title: str, only_active: bool) -> Optional[Match]:
    client = get_client()
    words = [w for w in title.split() if len(w) > 4][:3]
    if not words:
        return None
    q = client.table("stories").select("id,title,is_active")
    for w in words:
        q = q.ilike("title", f"%{w}%")
    if only_active:
        q = q.eq("is_active", True)
    res = q.limit(1).execute()
    rows = res.data or []
    if not rows:
        return None
    return Match(
        story_id=rows[0]["id"],
        title=rows[0]["title"],
        similarity=0.5,
        was_inactive=not rows[0].get("is_active", True),
    )


def find_match(title: str) -> Optional[Match]:
    """Look for an active match first; fall back to inactive (auto-revive)."""
    m = _query_similar(title, only_active=True)
    if m:
        return m
    m = _query_similar(title, only_active=False)
    if m and m.similarity >= STORY_SIMILARITY_THRESHOLD:
        return m
    return None
