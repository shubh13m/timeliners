"""One-shot: unstick events with identical event_timestamp on the same story.

For each (story_id, event_timestamp) group with >1 event, keep the earliest-
created one at its original time and bump each subsequent one by +N seconds
(ordered by created_at ascending so chronology of discovery is preserved).
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from ingest.db import get_client

c = get_client()
rows = (
    c.table("timeline_events")
    .select("id,story_id,event_timestamp,created_at,headline")
    .execute()
    .data
    or []
)

groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
for r in rows:
    groups[(r["story_id"], r["event_timestamp"])].append(r)

fixed = 0
for (sid, ts), members in groups.items():
    if len(members) < 2:
        continue
    # Sort by created_at ascending (earliest discovered first, keeps its ts).
    members.sort(key=lambda x: x["created_at"] or "")
    base = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    print(f"\nstory={sid[:8]}  ts={ts}  x{len(members)}")
    for i, m in enumerate(members):
        if i == 0:
            print(f"  keep     {m['headline'][:60]}")
            continue
        new_ts = (base + timedelta(seconds=i)).isoformat()
        c.table("timeline_events").update({"event_timestamp": new_ts}).eq("id", m["id"]).execute()
        print(f"  +{i}s -> {m['headline'][:60]}")
        fixed += 1

print(f"\nnudged {fixed} events")
