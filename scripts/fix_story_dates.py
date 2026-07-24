"""One-time backfill fixer: set each story's first_seen_at + last_updated to
the min/max of its timeline_events.event_timestamp.

Needed because the initial 14-day backfill stamped first_seen_at = now() for
every story, breaking chronological ordering and the "which date did this
break?" filter.
"""
from __future__ import annotations

from ingest.db import get_client


def main() -> None:
    c = get_client()
    stories = c.table("stories").select("id,title,first_seen_at,last_updated").execute().data
    updated = 0
    for s in stories:
        ev = (
            c.table("timeline_events")
            .select("event_timestamp")
            .eq("story_id", s["id"])
            .order("event_timestamp", desc=False)
            .execute()
            .data
        )
        if not ev:
            continue
        first = ev[0]["event_timestamp"]
        last = ev[-1]["event_timestamp"]
        # Only touch if the current first_seen_at differs from the true earliest event.
        payload = {}
        if s["first_seen_at"][:19] != first[:19]:
            payload["first_seen_at"] = first
        if s["last_updated"][:19] < last[:19]:
            payload["last_updated"] = last
        if not payload:
            continue
        c.table("stories").update(payload).eq("id", s["id"]).execute()
        updated += 1
        print(f"  {s['title'][:60]} -> first_seen={first[:10]} last={last[:10]}")
    print(f"\nDONE. Updated {updated}/{len(stories)} stories.")


if __name__ == "__main__":
    main()
