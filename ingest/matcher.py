"""Match clusters to existing DB stories using pg_trgm + keyword-overlap fallback."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

from .config import STORY_SIMILARITY_THRESHOLD
from .db import get_client
from .normalize import keyword_overlap, keywords, normalize_title

log = structlog.get_logger(__name__)

# Keyword-overlap threshold for the fallback matcher.
# 0.5 = half of the smaller keyword set must overlap. Empirically catches
# same-story different-source titles that trigram similarity misses,
# while avoiding false positives.
KEYWORD_MATCH_THRESHOLD: float = 0.5
MIN_KEYWORDS: int = 3
FALLBACK_LOOKBACK_DAYS: int = 14
FALLBACK_LIMIT: int = 500


@dataclass
class Match:
    story_id: str
    title: str
    similarity: float
    was_inactive: bool


def _query_similar(title: str, only_active: bool) -> Optional[Match]:
    """pg_trgm similarity via `match_story` RPC on normalized title."""
    client = get_client()
    q = normalize_title(title) or title
    try:
        res = client.rpc(
            "match_story",
            {
                "q": q,
                "only_active": only_active,
                "threshold": STORY_SIMILARITY_THRESHOLD,
            },
        ).execute()
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]
        return Match(
            story_id=row["id"],
            title=row["title"],
            similarity=float(row.get("similarity") or row.get("sim") or 0.0),
            was_inactive=not row.get("is_active", True),
        )
    except Exception as e:  # pragma: no cover
        log.debug("match_rpc_missing_fallback", error=str(e))
        return _fallback_ilike(title, only_active)


def _fallback_ilike(title: str, only_active: bool) -> Optional[Match]:
    """Last-resort ilike fallback if the RPC is unavailable."""
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


def _keyword_fallback(title: str, only_active: bool) -> Optional[Match]:
    """Fetch recent stories, score by keyword-set overlap in Python."""
    kws_new = keywords(title)
    if len(kws_new) < MIN_KEYWORDS:
        return None

    client = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=FALLBACK_LOOKBACK_DAYS)).isoformat()
    q = client.table("stories").select("id,title,is_active,last_updated").gte("last_updated", cutoff)
    if only_active:
        q = q.eq("is_active", True)
    rows = q.order("last_updated", desc=True).limit(FALLBACK_LIMIT).execute().data or []

    best: Optional[tuple[dict, float]] = None
    for row in rows:
        overlap = keyword_overlap(title, row["title"])
        if overlap >= KEYWORD_MATCH_THRESHOLD and (best is None or overlap > best[1]):
            best = (row, overlap)

    if not best:
        return None
    row, sim = best
    log.info(
        "keyword_fallback_match",
        similarity=round(sim, 3),
        new_title=title[:80],
        matched_title=row["title"][:80],
    )
    return Match(
        story_id=row["id"],
        title=row["title"],
        similarity=sim,
        was_inactive=not row.get("is_active", True),
    )


def find_match(title: str) -> Optional[Match]:
    """Look for an active match; fall back to inactive (auto-revive).

    Order per activity tier:
      1. pg_trgm similarity on normalized title.
      2. keyword-overlap fallback.
    """
    for only_active in (True, False):
        m = _query_similar(title, only_active=only_active)
        if m and m.similarity >= STORY_SIMILARITY_THRESHOLD:
            return m
        m = _keyword_fallback(title, only_active=only_active)
        if m:
            return m
    return None
