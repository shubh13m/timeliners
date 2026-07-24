"""One-shot: set stories.last_updated = max(timeline_events.event_timestamp)."""
from ingest.db import get_client

c = get_client()
stories = c.table("stories").select("id,last_updated").execute().data or []
print(f"scanning {len(stories)} stories...")
updated = 0
for row in stories:
    sid = row["id"]
    ev = (
        c.table("timeline_events")
        .select("event_timestamp")
        .eq("story_id", sid)
        .order("event_timestamp", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not ev:
        continue
    latest = ev[0]["event_timestamp"]
    if latest and latest != row["last_updated"]:
        c.table("stories").update({"last_updated": latest}).eq("id", sid).execute()
        updated += 1
print(f"updated {updated} rows")
