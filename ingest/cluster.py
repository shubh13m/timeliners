"""Cluster raw RSS articles into ~N story groups."""
from __future__ import annotations

import json
import re
from collections import defaultdict

import structlog

from .config import CLUSTER_CONFIDENCE_THRESHOLD, Settings
from .gemini import GeminiClient
from .rss import Article
from .schemas import ClusterOut, ClustersResponse

log = structlog.get_logger(__name__)

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "is", "was", "are", "were", "be", "been", "being", "as",
    "it", "its", "this", "that", "these", "those", "will", "would", "can",
    "could", "should", "may", "might", "has", "have", "had", "do", "does", "did",
    "not", "no", "yes", "says", "said", "new", "news", "india", "indian",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z']+", text.lower())
    return {w for w in words if len(w) > 3 and w not in _STOPWORDS}


def _cheap_cluster(articles: list[Article], target: int) -> list[list[int]]:
    """Greedy keyword-overlap clustering. Returns list of index-groups."""
    tokens = [_tokens(a.title + " " + a.snippet) for a in articles]
    n = len(articles)
    clusters: list[list[int]] = []
    cluster_tokens: list[set[str]] = []
    for i in range(n):
        best_j = -1
        best_score = 0.0
        for j, ct in enumerate(cluster_tokens):
            if not ct or not tokens[i]:
                continue
            inter = len(tokens[i] & ct)
            union = len(tokens[i] | ct)
            score = inter / union if union else 0.0
            if score > best_score:
                best_score = score
                best_j = j
        if best_score >= 0.25 and best_j >= 0:
            clusters[best_j].append(i)
            cluster_tokens[best_j] |= tokens[i]
        else:
            clusters.append([i])
            cluster_tokens.append(set(tokens[i]))
    # Sort by size desc, keep top `target * 2` for Gemini refinement.
    clusters.sort(key=len, reverse=True)
    return clusters[: target * 2]


def _format_articles_for_prompt(articles: list[Article], indices: list[int]) -> str:
    lines = []
    for idx in indices:
        a = articles[idx]
        lines.append(f"[{idx}] ({a.source}) {a.title} :: {a.snippet[:200]}")
    return "\n".join(lines)


def cluster_articles(
    articles: list[Article], settings: Settings, gemini: GeminiClient
) -> list[ClusterOut]:
    """Return up to `max_stories_per_run` high-confidence clusters."""
    if not articles:
        return []

    target = settings.max_stories_per_run
    raw_clusters = _cheap_cluster(articles, target)

    # If we have very few articles or all singletons, skip Gemini refinement.
    non_trivial = [c for c in raw_clusters if len(c) >= 2]
    if not non_trivial:
        log.info("cluster_all_singletons_skip_gemini")
        # Take top-N singletons by source credibility.
        singletons = sorted(
            raw_clusters, key=lambda c: -articles[c[0]].credibility
        )[:target]
        return [
            ClusterOut(
                title=articles[c[0]].title[:280],
                category="India Top News",
                article_indices=c,
                confidence=0.7,
            )
            for c in singletons
        ]

    candidate_indices = sorted({i for c in raw_clusters for i in c})
    prompt = (
        "You are a news editor. Below are today's raw news articles from Indian sources. "
        f"Group them into at most {target} distinct top stories. "
        "Merge articles that cover the same event/topic. Drop noise (ads, listicles, unrelated).\n\n"
        "Return STRICT JSON matching:\n"
        '{"clusters":[{"title":"...","category":"Politics|Sports|Business|Tech|Entertainment|India Top News",'
        '"article_indices":[..],"confidence":0.0-1.0}]}\n\n'
        f"Articles:\n{_format_articles_for_prompt(articles, candidate_indices)}\n"
    )

    try:
        resp = gemini.generate_json(prompt, ClustersResponse, phase="cluster")
    except Exception as e:
        log.warning("cluster_gemini_failed_falling_back", error=str(e))
        # Fallback: use cheap clusters as-is.
        return [
            ClusterOut(
                title=articles[c[0]].title[:280],
                category="India Top News",
                article_indices=c,
                confidence=0.65,
            )
            for c in raw_clusters[:target]
        ]

    valid_idx = set(range(len(articles)))
    kept: list[ClusterOut] = []
    for c in resp.clusters:
        c.article_indices = [i for i in c.article_indices if i in valid_idx]
        if not c.article_indices:
            continue
        if c.confidence < CLUSTER_CONFIDENCE_THRESHOLD:
            continue
        kept.append(c)
    kept = kept[:target]
    log.info("clusters_kept", count=len(kept))
    return kept
