"""Lifecycle sweep: mark stories inactive after N days of silence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog

from .config import Settings
from .db import get_client

log = structlog.get_logger(__name__)


def sweep_inactive(settings: Settings) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.inactive_days)).isoformat()
    client = get_client()
    res = (
        client.table("stories")
        .update({"is_active": False})
        .lt("last_updated", cutoff)
        .eq("is_active", True)
        .execute()
    )
    n = len(res.data or [])
    log.info("lifecycle_sweep", marked_inactive=n, cutoff=cutoff)
    return n
