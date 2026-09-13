"""Matching: exact key first, then a bounded fuzzy stage. No model, no randomness."""

from __future__ import annotations

from dataclasses import dataclass, field

from .normalize import normalize, tokens
from .table import Entry, Table

MATCHER_VERSION = "1.0.0"

#: Below this similarity nothing is returned: a wrong intent is worse than none.
DEFAULT_THRESHOLD = 0.75


@dataclass(frozen=True)
class Match:
    intent: str
    confidence: float
    #: "exact" or "fuzzy": how the decision was reached.
    stage: str
    phrase: str
    key: str
    slots: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)


def _similarity(left: list[str], right: list[str]) -> float:
    """Jaccard over words, order free and stable: same inputs, same number, always."""
    if not left or not right:
        return 0.0
    a, b = set(left), set(right)
    return len(a & b) / len(a | b)


def _stamp(table: Table, entry: Entry, stage: str) -> dict[str, str]:
    return {
        **table.provenance(),
        "matcher_version": MATCHER_VERSION,
        "stage": stage,
        "entry_phrase": entry.phrase,
        "entry_source": entry.source,
        "entry_added": entry.added,
        "entry_version": entry.version,
    }


def match(text: str, table: Table, threshold: float = DEFAULT_THRESHOLD) -> Match | None:
    """Best intent for `text`, or None when nothing clears the threshold."""
    key = normalize(text)
    exact = table.index.get(key)
    if exact is not None:
        return Match(
            intent=exact.intent,
            confidence=1.0,
            stage="exact",
            phrase=text,
            key=key,
            slots=dict(exact.slots),
            provenance=_stamp(table, exact, "exact"),
        )

    heard = tokens(text)
    best: tuple[float, Entry] | None = None
    for entry in table:
        score = _similarity(heard, entry.key.split())
        # Strictly greater keeps the first entry on a tie, so file order decides
        # and the result does not depend on dict iteration.
        if score > 0 and (best is None or score > best[0]):
            best = (score, entry)

    if best is None or best[0] < threshold:
        return None
    score, entry = best
    return Match(
        intent=entry.intent,
        confidence=round(score, 4),
        stage="fuzzy",
        phrase=text,
        key=key,
        slots=dict(entry.slots),
        provenance=_stamp(table, entry, "fuzzy"),
    )
