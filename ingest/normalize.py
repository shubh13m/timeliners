"""Title normalization + keyword extraction shared by matcher/dedup."""
from __future__ import annotations

import re

STOPWORDS: frozenset[str] = frozenset({
    "a","an","the","and","or","of","in","on","at","to","for","from","by","with","as","is","are","was","were",
    "be","been","being","this","that","these","those","it","its","he","she","they","them","his","her","their",
    "will","would","could","should","may","might","can","says","said","new","top","live","updates","update",
    "more","after","before","over","under","amid","vs","via","also","just","today","now","latest","how","why",
    "what","who","when","where","which","than","then","into","out","up","down","off","one","two","three",
})

# Common Indian & international publisher suffixes. Lowercase, no leading dash.
_PUBS: tuple[str, ...] = (
    "the times of india","times of india","hindustan times","the hindu","ndtv","indian express",
    "the indian express","ap news","associated press","reuters","bbc news","bbc","cnn","al jazeera",
    "the wire","scroll.in","firstpost","moneycontrol","business standard","livemint","mint",
    "the economic times","economic times","news18","india today","zee news","republic","times now",
    "the print","theprint","the quint","thequint","the tribune","tribune india","deccan herald",
    "deccan chronicle","the new indian express","new indian express","the telegraph","telegraph india",
    "outlook","outlook india","dna","dna india","opindia","the statesman","statesman",
)

_PUB_RE = re.compile(
    r"\s*[\-\|:—–]+\s*(" + "|".join(re.escape(p) for p in sorted(_PUBS, key=len, reverse=True)) + r")\s*$",
    re.IGNORECASE,
)
_MARKER_RE = re.compile(
    r"\b(live|breaking|exclusive|update|updates|latest|watch|explained)\b[:\s\-–—]*",
    re.IGNORECASE,
)
_NON_WORD_RE = re.compile(r"[^\w\s]")
_MULTI_WS_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Lowercase, strip publisher suffix and noise markers, remove punctuation."""
    if not title:
        return ""
    x = title.strip()
    # Repeatedly strip publisher suffixes (some titles have double)
    for _ in range(2):
        new = _PUB_RE.sub("", x)
        if new == x:
            break
        x = new
    x = x.lower()
    x = _MARKER_RE.sub(" ", x)
    x = _NON_WORD_RE.sub(" ", x)
    x = _MULTI_WS_RE.sub(" ", x).strip()
    return x


def keywords(title: str) -> set[str]:
    """Content keywords (>2 chars, non-stopword) from a title."""
    return {
        w for w in normalize_title(title).split()
        if len(w) > 2 and w not in STOPWORDS
    }


def keyword_overlap(a: str, b: str) -> float:
    """Jaccard-like overlap normalized by the smaller set."""
    ka, kb = keywords(a), keywords(b)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / min(len(ka), len(kb))
