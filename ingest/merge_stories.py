"""Merge duplicate stories detected after-the-fact.

Usage:
    python -m ingest.merge_stories <keep_slug_or_id> <drop_slug_or_id> [<drop2> ...]

Moves all timeline_events from the dropped stories into the kept story,
recomputes trending_score, keeps kept story's earliest first_seen_at,
then deletes the dropped stories.
"""
from __future__ import annotations

import sys
from typing import Optional

import structlog

from .db import get_client

log = structlog.get_logger(__name__)


def _resolve(client, ref: str) -> Optional[dict]:
    """Resolve a story by UUID or slug."""
    # try UUID
    try:
        r = client.table("stories").select("*").eq("id", ref).limit(1).execute()
        if r.data:
            return r.data[0]
    except Exception:
        pass
    r = client.table("stories").select("*").eq("slug", ref).limit(1).execute()
    return r.data[0] if r.data else None


def merge(keep_ref: str, drop_refs: list[str]) -> None:
    client = get_client()
    keep = _resolve(client, keep_ref)
    if not keep:
        raise SystemExit(f"keep story not found: {keep_ref}")

    keep_id = keep["id"]
    print(f"KEEP: {keep_id}  {keep['title'][:80]}")

    for drop_ref in drop_refs:
        drop = _resolve(client, drop_ref)
        if not drop:
            print(f"  drop not found, skipping: {drop_ref}")
            continue
        drop_id = drop["id"]
        if drop_id == keep_id:
            print(f"  skip self-merge: {drop_id}")
            continue
        print(f"DROP: {drop_id}  {drop['title'][:80]}")

        # Move events. Duplicates on (story_id, content_hash) are handled by upsert-conflict.
        events = client.table("timeline_events").select("*").eq("story_id", drop_id).execute().data or []
        moved = 0
        for e in events:
            e["story_id"] = keep_id
            e.pop("id", None)
            try:
                client.table("timeline_events").upsert(
                    e, on_conflict="story_id,content_hash", ignore_duplicates=True
                ).execute()
                moved += 1
            except Exception as ex:
                print(f"    event move failed: {ex}")
        print(f"  moved {moved}/{len(events)} events")

        # Merge earliest first_seen_at and latest last_updated
        keep_first = min(keep["first_seen_at"], drop["first_seen_at"])
        keep_last = max(keep["last_updated"], drop["last_updated"])
        client.table("stories").update(
            {"first_seen_at": keep_first, "last_updated": keep_last}
        ).eq("id", keep_id).execute()

        # Delete drop rows: events (should be 0 left after upsert), then story
        client.table("timeline_events").delete().eq("story_id", drop_id).execute()
        client.table("stories").delete().eq("id", drop_id).execute()
        print(f"  deleted story {drop_id}")

    # Recompute trending_score = event count of kept story
    ev = client.table("timeline_events").select("id", count="exact").eq("story_id", keep_id).execute()
    count = ev.count or 0
    client.table("stories").update({"trending_score": count}).eq("id", keep_id).execute()
    print(f"DONE. keep {keep_id} now has {count} events.")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(2)
    keep = sys.argv[1]
    drops = sys.argv[2:]
    merge(keep, drops)


if __name__ == "__main__":
    main()
