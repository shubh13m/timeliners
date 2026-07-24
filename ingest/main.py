"""Orchestrator for the Timeliner ingest pipeline."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

import structlog

from . import cluster as cluster_mod
from . import curator, dedup, lifecycle, matcher, persist, push, rss
from .config import load_settings
from .gemini import CircuitBreakerOpen, GeminiClient
from .schemas import EventsResponse


def _setup_logging() -> None:
    logging.basicConfig(
        format="%(message)s", stream=sys.stdout, level=logging.INFO
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


log = structlog.get_logger("ingest")


def _build_events_prompt(clusters_with_context: list[dict]) -> str:
    return (
        "You are a structured news analyst building a chronological TIMELINE for each story.\n"
        "For each story below, extract ONLY NEW chronological events not already in existing_timeline.\n\n"
        "RULES:\n"
        "1. Break the story into 2-4 DISTINCT events when the articles contain enough substance "
        "(e.g. an announcement + a reaction + a follow-up = 3 events). If only one significant "
        "development is reported, return exactly one event.\n"
        "2. The event `headline` must describe WHAT HAPPENED with specifics (an action, decision, "
        "statement, outcome). Do NOT restate or paraphrase the story title.\n"
        "3. `details` must be 2-3 complete sentences with concrete facts: who, when, where, "
        "numbers, direct quotes if present. Never restate the headline. Never say 'this event' "
        "or 'the story'. Write it like a wire-service dispatch.\n"
        "4. `event_timestamp` = the article's published time (ISO 8601, with timezone).\n"
        "5. Set `event_type` to the best-fit label.\n"
        "6. Drop events with confidence < 0.6.\n\n"
        "Return STRICT JSON:\n"
        '{"stories":[{"cluster_index":int,"updated_summary":"one-sentence neutral overview",'
        '"new_events":[{"event_timestamp":"ISO8601","headline":"...","details":"...",'
        '"event_type":"announcement|verdict|statement|update|correction",'
        '"source_index":int,"confidence":0.0-1.0}]}]}\n\n'
        "If a cluster has no new events, return an empty new_events list for it.\n"
        "`source_index` is the index into that cluster's articles.\n\n"
        f"Input:\n{json.dumps(clusters_with_context, indent=2, default=str)}\n"
    )


def process_articles(
    articles: list, settings, gemini: GeminiClient, dry_run: bool = False
) -> tuple[int, int]:
    """Cluster → match → dedup → generate events → persist.

    Returns (stories_updated, events_inserted).
    Extracted from run() so backfill can reuse the same pipeline.
    """
    if not articles:
        return 0, 0

    # Phase 2: cluster
    try:
        clusters = cluster_mod.cluster_articles(articles, settings, gemini)
    except CircuitBreakerOpen as e:
        log.error("circuit_breaker_open", stage="cluster", error=str(e))
        raise
    if not clusters:
        log.info("no_clusters")
        return 0, 0

    # Phases 3+4: match existing stories, filter dedup, build prompt input
    prompt_input: list[dict] = []
    per_cluster_state: list[dict] = []

    for idx, c in enumerate(clusters):
        cluster_articles = [articles[i] for i in c.article_indices]
        match = matcher.find_match(c.title)
        story_id = match.story_id if match else None
        seen = dedup.existing_hashes(story_id) if story_id else set()
        new_articles = dedup.filter_new(cluster_articles, seen)
        if not new_articles and story_id:
            log.info("cluster_fully_deduped_skipping", cluster_index=idx, title=c.title[:80])
            continue

        existing_events = dedup.existing_timeline(story_id) if story_id else []
        prompt_input.append(
            {
                "cluster_index": idx,
                "title": c.title,
                "category": c.category,
                "existing_summary": None,
                "existing_timeline": existing_events,
                "articles": [
                    {
                        "index": i,
                        "source": a.source,
                        "url": a.url,
                        "published_at": a.published_at.isoformat(),
                        "title": a.title,
                        "snippet": a.snippet,
                    }
                    for i, a in enumerate(new_articles)
                ],
            }
        )
        per_cluster_state.append(
            {
                "cluster_index": idx,
                "cluster": c,
                "story_id": story_id,
                "was_inactive": bool(match and match.was_inactive),
                "new_articles": new_articles,
            }
        )

    if not prompt_input:
        log.info("nothing_new_after_dedup")
        return 0, 0

    # Phase 5: batched Gemini call for events
    prompt = _build_events_prompt(prompt_input)
    try:
        events_resp: EventsResponse = gemini.generate_json(
            prompt, EventsResponse, phase="events"
        )
    except CircuitBreakerOpen:
        raise
    except Exception as e:
        log.error("events_call_failed", error=str(e))
        return 0, 0

    # Phases 6+7: persist + intra-run dedup
    total_events = 0
    stories_updated: list[tuple[str, str, str, str]] = []
    resp_by_idx = {s.cluster_index: s for s in events_resp.stories}
    persisted_new: list[tuple[str, str]] = []
    from .normalize import keyword_overlap

    for state in per_cluster_state:
        idx = state["cluster_index"]
        s_out = resp_by_idx.get(idx)
        if not s_out or not s_out.new_events:
            continue
        cluster = state["cluster"]

        if not state["story_id"]:
            for existing_id, existing_title in persisted_new:
                if keyword_overlap(cluster.title, existing_title) >= 0.5:
                    log.info(
                        "intra_run_merge",
                        cluster_index=idx,
                        title=cluster.title[:80],
                        merged_into=existing_title[:80],
                    )
                    state["story_id"] = existing_id
                    break

        first_seen = date.today()
        slug = persist.make_slug(cluster.title, first_seen)
        if dry_run:
            log.info(
                "dry_run_would_persist",
                cluster_index=idx,
                title=cluster.title[:80],
                events=len(s_out.new_events),
            )
            continue
        was_new = state["story_id"] is None
        earliest = None
        articles_for_state = state.get("new_articles") or []
        if articles_for_state:
            earliest = min(a.published_at for a in articles_for_state if a.published_at)
        story_id = persist.upsert_story(
            story_id=state["story_id"],
            title=cluster.title,
            category=cluster.category,
            summary=s_out.updated_summary or "",
            was_inactive=state["was_inactive"],
            first_seen_ts=earliest,
        )
        inserted = persist.insert_events(story_id, s_out.new_events, state["new_articles"])
        if inserted:
            total_events += inserted
            persist.upsert_daily_digest(
                story_id, s_out.updated_summary or cluster.title, display_order=idx
            )
            persist.refresh_trending_score(story_id)
            slug_res = (
                persist.get_client().table("stories").select("slug,title")
                .eq("id", story_id).limit(1).execute()
            )
            row = (slug_res.data or [{}])[0]
            db_title = row.get("title") or cluster.title
            db_slug = row.get("slug") or slug
            stories_updated.append(
                (story_id, db_title, db_slug, s_out.new_events[0].headline)
            )
            if was_new:
                persisted_new.append((story_id, db_title))

    if not dry_run:
        for story_id, title, slug, headline in stories_updated:
            push.notify_story_update(settings, story_id, title, slug, headline)

    return len(stories_updated), total_events


def run(dry_run: bool = False) -> int:
    settings = load_settings()
    log.info("run_start", dry_run=dry_run, model=settings.gemini_model)

    articles = rss.fetch_all(settings)
    if not articles:
        log.warning("no_articles_exiting")
        return 0

    gemini = GeminiClient(settings)

    try:
        stories_updated, events_inserted = process_articles(
            articles, settings, gemini, dry_run=dry_run
        )
    except CircuitBreakerOpen:
        return 2

    # Post-ingest AI curator: dedupe stragglers the deterministic matcher missed,
    # flag misplaced timeline events. Best-effort — errors here don't fail the run.
    if not dry_run:
        try:
            curator.run_curator(settings, gemini=gemini, dry_run=False)
        except Exception as e:  # pragma: no cover
            log.warning("curator_stage_failed", error=str(e))

    lifecycle.sweep_inactive(settings)

    log.info(
        "run_complete",
        stories_updated=stories_updated,
        events_inserted=events_inserted,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="timeliner-ingest")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    args = parser.parse_args()
    _setup_logging()
    try:
        return run(dry_run=args.dry_run)
    except Exception as e:
        log.exception("run_failed", error=str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
