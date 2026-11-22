"""Small text utilities shared by the heuristic auditor and the eval baselines."""

import re

STOPWORDS = frozenset(
    """a an the and or but if then so of to in on at for from by with about as into over after
    before is are was were be been being am do does did done have has had having i me my mine we
    our you your he she it its they them their this that these those there here what which who
    whom when where why how all any both each few more most other some such nor only own same than
    too very can will just should would could might must shall may also up down out off again
    further once i'll i'm i've it's that's get got""".split()
)

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|;\s*")


def words(text: str) -> list[str]:
    """Lowercase word tokens. Matching on tokens (not substrings) is the fix for v1's
    `"not" in "another"` class of bugs."""
    return _WORD.findall(text.lower())


def stem(word: str) -> str:
    for suffix in ("ing", "ed", "s"):
        if word.endswith(suffix) and not word.endswith("ss") and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def content_words(text: str) -> list[str]:
    return [stem(w) for w in words(text) if w not in STOPWORDS and len(w) > 1]


def sentences(text: str) -> list[str]:
    parts = (p.strip(" .!?;,") for p in _SENTENCE_SPLIT.split(text))
    return [p for p in parts if p]


def overlap_coefficient(a: str, b: str) -> float:
    """|A ∩ B| / min(|A|, |B|) over content-word stems; 0.0 when either side is empty."""
    sa, sb = set(content_words(a)), set(content_words(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def normalize_for_match(text: str) -> str:
    return " ".join(words(text))
