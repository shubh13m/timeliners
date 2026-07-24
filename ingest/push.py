"""Web Push dispatch via pywebpush (VAPID)."""
from __future__ import annotations

import json

import structlog
from pywebpush import WebPushException, webpush

from .config import Settings
from .db import get_client

log = structlog.get_logger(__name__)


def _subscriptions_for_story(story_id: str) -> list[dict]:
    """Return subscriptions whose story_filter matches this story or is empty (all)."""
    res = get_client().table("push_subscriptions").select("*").execute()
    subs = res.data or []
    matched = []
    for s in subs:
        f = s.get("story_filter") or {}
        stories = f.get("stories") if isinstance(f, dict) else None
        if not stories or story_id in stories:
            matched.append(s)
    return matched


def notify_story_update(
    settings: Settings, story_id: str, story_title: str, slug: str, headline: str
) -> int:
    if not settings.vapid_private_key:
        log.info("push_skipped_no_vapid")
        return 0

    subs = _subscriptions_for_story(story_id)
    if not subs:
        return 0

    payload = json.dumps(
        {
            "title": story_title[:80],
            "body": headline[:160],
            "url": f"/story/{slug}",
        }
    )

    sent = 0
    stale: list[str] = []
    for s in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": s["endpoint"],
                    "keys": {"p256dh": s["p256dh"], "auth": s["auth"]},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
                ttl=3600,
            )
            sent += 1
        except WebPushException as e:
            status = getattr(getattr(e, "response", None), "status_code", 0)
            if status in (404, 410):
                stale.append(s["endpoint"])
            else:
                log.warning("push_failed", endpoint=s["endpoint"][:60], status=status)
        except Exception as e:
            log.warning("push_error", error=str(e))

    if stale:
        client = get_client()
        for ep in stale:
            client.table("push_subscriptions").delete().eq("endpoint", ep).execute()
        log.info("push_pruned_stale", count=len(stale))

    log.info("push_sent", story_id=story_id, sent=sent, subs=len(subs))
    return sent
