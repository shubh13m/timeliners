"""RSS feed fetching with ETag / Last-Modified caching."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import feedparser
import httpx
import structlog

from .config import RSS_SOURCES, Settings

log = structlog.get_logger(__name__)


@dataclass
class Article:
    title: str
    url: str
    published_at: datetime
    source: str
    snippet: str
    credibility: float

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()


def _cache_path(settings: Settings, source_name: str) -> Path:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", source_name).strip("_").lower()
    return settings.cache_dir / f"{safe}.meta.json"


def _load_cache(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:600]


def _parse_time(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def fetch_source(source: dict, settings: Settings) -> list[Article]:
    cache_path = _cache_path(settings, source["name"])
    cache = _load_cache(cache_path)

    headers = {"User-Agent": "TimelinerBot/1.0 (+https://github.com/shubh13m/timeliners)"}
    if cache.get("etag"):
        headers["If-None-Match"] = cache["etag"]
    if cache.get("last_modified"):
        headers["If-Modified-Since"] = cache["last_modified"]

    try:
        resp = httpx.get(source["url"], headers=headers, timeout=20, follow_redirects=True)
    except Exception as e:
        log.warning("rss_fetch_failed", source=source["name"], error=str(e))
        return []

    if resp.status_code == 304:
        log.info("rss_not_modified", source=source["name"])
        return []
    if resp.status_code != 200:
        log.warning("rss_bad_status", source=source["name"], status=resp.status_code)
        return []

    new_cache = {}
    if "ETag" in resp.headers:
        new_cache["etag"] = resp.headers["ETag"]
    if "Last-Modified" in resp.headers:
        new_cache["last_modified"] = resp.headers["Last-Modified"]
    if new_cache:
        _save_cache(cache_path, new_cache)

    parsed = feedparser.parse(resp.content)
    credibility = float(source.get("credibility", 0.8))
    articles: list[Article] = []
    for e in parsed.entries:
        title = (getattr(e, "title", "") or "").strip()
        url = (getattr(e, "link", "") or "").strip()
        if not title or not url:
            continue
        snippet = _clean_html(getattr(e, "summary", "") or getattr(e, "description", "") or "")
        articles.append(
            Article(
                title=title,
                url=url,
                published_at=_parse_time(e),
                source=source["name"],
                snippet=snippet,
                credibility=credibility,
            )
        )
    log.info("rss_fetched", source=source["name"], count=len(articles))
    return articles


def fetch_all(settings: Settings) -> list[Article]:
    all_articles: list[Article] = []
    for src in RSS_SOURCES:
        all_articles.extend(fetch_source(src, settings))
    # Dedupe by URL across sources.
    seen: set[str] = set()
    unique: list[Article] = []
    for a in all_articles:
        if a.url in seen:
            continue
        seen.add(a.url)
        unique.append(a)
    log.info("rss_total_unique", count=len(unique))
    return unique


def article_to_dict(a: Article) -> dict:
    d = asdict(a)
    d["published_at"] = a.published_at.isoformat()
    d["content_hash"] = a.content_hash
    return d
