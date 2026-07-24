"""Post-ingest AI curator: dedupe near-duplicate stories and flag misplaced events.

This runs once at the end of every ingest cycle (and every backfill day) as a
belt-and-braces cleanup on top of the deterministic matcher. It sends a batched
snapshot of recent stories + their top event headlines to Gemini and applies
high-confidence merges automatically.

Three concerns it addresses at once:
  1. Dedup: merges duplicate stories the deterministic matcher missed.
  2. New vs existing: if the matcher created a NEW story that should have
     appended to an existing one, curator merges them post-facto.
  3. Timeline coherence: flags events that don't belong to their story so
     they can be reviewed. (We only *flag* misplaced events for now; auto-
     removing them is riskier than auto-merging duplicate stories.)

Cost: one batched Gemini call per ingest run. On flash-lite free tier this is
essentially free (~5k input tokens, well under the 1M/min limit).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

from . import merge_stories
from .config import Settings, load_settings
from .db import get_client
from .gemini import CircuitBreakerOpen, GeminiClient
from .schemas import CuratorResponse

log = structlog.get_logger(__name__)

# Only look at stories active in this window. Curator focuses on recent noise,
# not stories that have already been archived / cooled off.
LOOKBACK_DAYS: int = 14
# Cap payload size so the prompt stays cheap even after months of accumulation.
MAX_STORIES: int = 60
# Only auto-apply merges this confident. Below this, we log for review.
AUTO_MERGE_CONFIDENCE: float = 0.85


def _fetch_recent_stories() -> list[dict]:
    """Fetch active stories in the lookback window + their top 3 event headlines."""
    client = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    rows = (
        client.table("stories")
        .select("id,slug,title,category,first_seen_at,last_updated")
        .eq("is_active", True)
        .gte("last_updated", cutoff)
        .order("last_updated", desc=True)
        .limit(MAX_STORIES)
        .execute()
        .data
        or []
    )
    if not rows:
        return []

    ids = [r["id"] for r in rows]
    events = (
        client.table("timeline_events")
        .select("story_id,headline,event_timestamp")
        .in_("story_id", ids)
        .order("event_timestamp", desc=True)
        .execute()
        .data
        or []
    )
    by_story: dict[str, list[dict]] = {}
    for e in events:
        by_story.setdefault(e["story_id"], []).append(e)

    out: list[dict] = []
    for r in rows:
        top = by_story.get(r["id"], [])[:3]
        out.append(
            {
                "slug": r["slug"],
                "title": r["title"],
                "category": r["category"],
                "first_seen": (r.get("first_seen_at") or "")[:10],
                "last_updated": (r.get("last_updated") or "")[:10],
                "recent_events": [e["headline"] for e in top],
            }
        )
    return out


def _build_prompt(stories: list[dict]) -> str:
    return (
        "You are an editorial curator reviewing a news timeline database.\n\n"
        "For the stories below, do TWO tasks:\n\n"
        "TASK 1 - DUPLICATES: Identify pairs that describe the SAME real-world "
        "underlying story (not merely the same topic or the same person). Signals: "
        "same actors, same incident, same court case, same series, or one is a clear "
        "update / continuation of the other. Different matches in a cricket series "
        "are DIFFERENT stories. Different press conferences by the same politician on "
        "different topics are DIFFERENT stories.\n"
        "  - Prefer keeping the story with more events and the more descriptive title.\n"
        "  - Only flag pairs you are confident about (>= 0.7). Report your confidence.\n\n"
        "TASK 2 - MISPLACED EVENTS: If any listed `recent_events` headline clearly "
        "does not belong to the story it's attached to (e.g. an unrelated topic slipped "
        "in during clustering), flag it. Do NOT flag events just because they are minor "
        "or repetitive.\n\n"
        "Return STRICT JSON:\n"
        '{"duplicates":[{"keep_slug":"...","drop_slug":"...","confidence":0.0-1.0,'
        '"reason":"one sentence"}],'
        '"misplaced_events":[{"story_slug":"...","event_headline":"...","reason":"..."}]}\n\n'
        "Empty arrays are fine if nothing warrants action.\n\n"
        f"Stories:\n{json.dumps(stories, indent=2, ensure_ascii=False)}\n"
    )


def _apply_duplicates(
    pairs: list, known_slugs: set[str], dry_run: bool
) -> tuple[int, int]:
    """Apply high-confidence merges. Return (applied, flagged_low_confidence)."""
    applied = 0
    flagged = 0
    # Track slugs that have been dropped so we don't try to reference them again
    # if the model chains merges (A->B and B->C).
    dropped: set[str] = set()

    for p in pairs:
        if p.keep_slug == p.drop_slug:
            continue
        if p.keep_slug not in known_slugs or p.drop_slug not in known_slugs:
            log.warning(
                "curator_unknown_slug",
                keep=p.keep_slug,
                drop=p.drop_slug,
                reason=p.reason,
            )
            continue
        if p.drop_slug in dropped or p.keep_slug in dropped:
            log.info(
                "curator_skipping_chained_merge",
                keep=p.keep_slug,
                drop=p.drop_slug,
            )
            continue

        if p.confidence < AUTO_MERGE_CONFIDENCE:
            log.info(
                "curator_low_confidence_flag",
                keep=p.keep_slug,
                drop=p.drop_slug,
                confidence=round(p.confidence, 2),
                reason=p.reason,
            )
            flagged += 1
            continue

        log.info(
            "curator_merge",
            keep=p.keep_slug,
            drop=p.drop_slug,
            confidence=round(p.confidence, 2),
            reason=p.reason,
            dry_run=dry_run,
        )
        if not dry_run:
            try:
                merge_stories.merge(p.keep_slug, [p.drop_slug])
                dropped.add(p.drop_slug)
                applied += 1
            except (Exception, SystemExit) as e:
                log.error(
                    "curator_merge_failed",
                    keep=p.keep_slug,
                    drop=p.drop_slug,
                    error=str(e),
                )
        else:
            applied += 1
    return applied, flagged


def run_curator(
    settings: Settings, gemini: Optional[GeminiClient] = None, dry_run: bool = False
) -> dict:
    """Fetch recent stories, ask Gemini for dedup + coherence, apply high-confidence merges.

    Safe to call even when there are 0 or 1 stories to review (returns early).
    Returns a summary dict for logging.
    """
    stories = _fetch_recent_stories()
    if len(stories) < 2:
        log.info("curator_skip_too_few", n=len(stories))
        return {"reviewed": len(stories), "merged": 0, "flagged": 0, "misplaced": 0}

    log.info("curator_start", reviewed=len(stories), dry_run=dry_run)
    gemini = gemini or GeminiClient(settings)
    prompt = _build_prompt(stories)
    try:
        resp: CuratorResponse = gemini.generate_json(
            prompt, CuratorResponse, phase="curator"
        )
    except CircuitBreakerOpen:
        log.error("curator_circuit_open")
        return {"reviewed": len(stories), "merged": 0, "flagged": 0, "misplaced": 0}
    except Exception as e:
        log.error("curator_call_failed", error=str(e))
        return {"reviewed": len(stories), "merged": 0, "flagged": 0, "misplaced": 0}

    known = {s["slug"] for s in stories}
    merged, flagged = _apply_duplicates(resp.duplicates, known, dry_run=dry_run)

    for m in resp.misplaced_events:
        log.warning(
            "curator_misplaced_event",
            story_slug=m.story_slug,
            headline=m.event_headline[:120],
            reason=m.reason,
        )

    summary = {
        "reviewed": len(stories),
        "duplicates_proposed": len(resp.duplicates),
        "merged": merged,
        "flagged": flagged,
        "misplaced": len(resp.misplaced_events),
    }
    log.info("curator_complete", **summary)
    return summary


def main() -> int:
    """Standalone CLI: `python -m ingest.curator [--dry-run]`."""
    import argparse

    from .main import _setup_logging

    parser = argparse.ArgumentParser(prog="timeliner-curator")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _setup_logging()
    settings = load_settings()
    try:
        run_curator(settings, dry_run=args.dry_run)
        return 0
    except Exception as e:
        log.exception("curator_failed", error=str(e))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
