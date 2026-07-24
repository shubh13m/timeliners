"""Monthly cold archive: export inactive-old stories to repo JSON, then delete from DB."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import structlog

from .config import Settings, load_settings
from .db import get_client

log = structlog.get_logger(__name__)


def _archive_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "archive"


def run_archive(settings: Settings | None = None) -> int:
    settings = settings or load_settings()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.archive_days)).isoformat()
    client = get_client()

    stories = (
        client.table("stories")
        .select("*")
        .eq("is_active", False)
        .lt("last_updated", cutoff)
        .execute()
    ).data or []

    if not stories:
        log.info("archive_nothing_to_do")
        return 0

    story_ids = [s["id"] for s in stories]
    events = (
        client.table("timeline_events")
        .select("*")
        .in_("story_id", story_ids)
        .execute()
    ).data or []
    digests = (
        client.table("daily_digests")
        .select("*")
        .in_("story_id", story_ids)
        .execute()
    ).data or []

    out_dir = _archive_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"{date.today().strftime('%Y-%m')}.json"
    existing = {}
    if fname.exists():
        try:
            existing = json.loads(fname.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stories": (existing.get("stories") or []) + stories,
        "timeline_events": (existing.get("timeline_events") or []) + events,
        "daily_digests": (existing.get("daily_digests") or []) + digests,
    }
    fname.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    log.info("archive_written", file=str(fname), stories=len(stories))

    # Delete from DB (cascades to events + digests).
    for sid in story_ids:
        client.table("stories").delete().eq("id", sid).execute()
    log.info("archive_deleted_from_db", count=len(story_ids))
    return len(story_ids)


if __name__ == "__main__":
    structlog.configure()
    run_archive()
