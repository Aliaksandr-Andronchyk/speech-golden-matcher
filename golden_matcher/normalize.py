"""Text normalisation: the only place where a phrase loses its shape.

Everything here is deterministic and version tagged. Changing any rule means
bumping NORMALIZER_VERSION, because it changes which key a phrase maps to.
"""

from __future__ import annotations

import re
import unicodedata

NORMALIZER_VERSION = "1.1.0"

_PUNCTUATION = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACES = re.compile(r"\s+", flags=re.UNICODE)

# Spoken forms the recogniser produces for digits. Kept tiny and explicit:
# a golden table is only useful while every rule in it can be read by a human.
_NUMBERS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}

_FILLERS = frozenset({"uh", "um", "erm", "hmm", "like", "well"})

# Contractions are expanded before punctuation is stripped, otherwise "what's"
# becomes the two words "what s" and never lines up with a golden "what is".
_CONTRACTIONS = {
    "what's": "what is",
    "that's": "that is",
    "it's": "it is",
    "let's": "let us",
    "how's": "how is",
    "where's": "where is",
    "who's": "who is",
    "i'm": "i am",
    "don't": "do not",
    "can't": "can not",
    "won't": "will not",
}

_CONTRACTION_RE = re.compile(
    r"\b(?:%s)\b" % "|".join(re.escape(word) for word in _CONTRACTIONS), flags=re.UNICODE
)


def normalize(text: str) -> str:
    """Maps a phrase to its lookup key: lowercase words, no punctuation, no fillers."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    folded = folded.replace("’", "'").replace("`", "'")
    folded = _CONTRACTION_RE.sub(lambda found: _CONTRACTIONS[found.group(0)], folded)
    folded = _PUNCTUATION.sub(" ", folded)
    words = [_NUMBERS.get(word, word) for word in _SPACES.split(folded) if word]
    kept = [word for word in words if word not in _FILLERS]
    # A phrase of nothing but fillers keeps them: an empty key matches everything.
    return " ".join(kept or words)


def tokens(text: str) -> list[str]:
    """Normalised phrase split into words, used by the fuzzy stage."""
    key = normalize(text)
    return key.split() if key else []
