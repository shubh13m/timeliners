"""Central configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env.local from repo root when running locally.
_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env.local", override=False)


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required env var: {key}")
    return val


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_key: str
    gemini_api_key: str
    gemini_model: str
    vapid_public_key: str
    vapid_private_key: str
    vapid_subject: str
    max_stories_per_run: int
    inactive_days: int
    archive_days: int
    cache_dir: Path


def load_settings() -> Settings:
    return Settings(
        supabase_url=_require("SUPABASE_URL"),
        supabase_service_key=_require("SUPABASE_SERVICE_KEY"),
        gemini_api_key=_require("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        vapid_public_key=os.getenv("VAPID_PUBLIC_KEY", ""),
        vapid_private_key=os.getenv("VAPID_PRIVATE_KEY", ""),
        vapid_subject=os.getenv("VAPID_SUBJECT", "mailto:admin@example.com"),
        max_stories_per_run=_int("INGEST_MAX_STORIES_PER_RUN", 10),
        inactive_days=_int("INGEST_INACTIVE_DAYS", 14),
        archive_days=_int("INGEST_ARCHIVE_DAYS", 90),
        cache_dir=_REPO_ROOT / "ingest" / ".cache",
    )


# RSS sources — Google News India, one endpoint per topic.
# All feeds are free, unauthenticated, English, India edition.
_GN_BASE = "https://news.google.com/rss"
_GN_TOPIC = f"{_GN_BASE}/headlines/section/topic"
_GN_SUFFIX = "hl=en-IN&gl=IN&ceid=IN:en"

RSS_SOURCES: list[dict[str, str]] = [
    {
        "name": "Google News India — Top",
        "url": f"{_GN_BASE}?{_GN_SUFFIX}",
        "credibility": "0.7",
        "category_hint": "India Top News",
    },
    {
        "name": "Google News India — World",
        "url": f"{_GN_TOPIC}/WORLD?{_GN_SUFFIX}",
        "credibility": "0.7",
        "category_hint": "World",
    },
    {
        "name": "Google News India — Business",
        "url": f"{_GN_TOPIC}/BUSINESS?{_GN_SUFFIX}",
        "credibility": "0.7",
        "category_hint": "Business",
    },
    {
        "name": "Google News India — Technology",
        "url": f"{_GN_TOPIC}/TECHNOLOGY?{_GN_SUFFIX}",
        "credibility": "0.7",
        "category_hint": "Technology",
    },
    {
        "name": "Google News India — Sports",
        "url": f"{_GN_TOPIC}/SPORTS?{_GN_SUFFIX}",
        "credibility": "0.7",
        "category_hint": "Sports",
    },
    {
        "name": "Google News India — Entertainment",
        "url": f"{_GN_TOPIC}/ENTERTAINMENT?{_GN_SUFFIX}",
        "credibility": "0.7",
        "category_hint": "Entertainment",
    },
    {
        "name": "Google News India — Science",
        "url": f"{_GN_TOPIC}/SCIENCE?{_GN_SUFFIX}",
        "credibility": "0.7",
        "category_hint": "Technology",
    },
    {
        "name": "Google News India — Health",
        "url": f"{_GN_TOPIC}/HEALTH?{_GN_SUFFIX}",
        "credibility": "0.7",
        "category_hint": "India Top News",
    },
]

# Rate-limit guard: minimum seconds between Gemini calls.
GEMINI_MIN_INTERVAL_S: float = 5.0

# Circuit breaker: abort run after N consecutive Gemini failures.
GEMINI_MAX_CONSECUTIVE_FAILURES: int = 3

# Confidence threshold to keep a cluster.
CLUSTER_CONFIDENCE_THRESHOLD: float = 0.6

# Story matching threshold (pg_trgm similarity).
STORY_SIMILARITY_THRESHOLD: float = 0.4
