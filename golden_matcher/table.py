"""The golden table: JSONL on disk, one entry per line, with provenance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from .normalize import NORMALIZER_VERSION, normalize

TABLE_FORMAT_VERSION = "1"


class TableError(ValueError):
    """A line of the table cannot be trusted, so the whole table is refused."""


@dataclass(frozen=True)
class Entry:
    """One golden phrase and what it means."""

    phrase: str
    intent: str
    #: Where this line came from: recording id, ticket, person. Never empty.
    source: str
    #: Date the line was added, ISO 8601.
    added: str
    version: str = "1"
    slots: dict[str, str] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return normalize(self.phrase)

    def to_json(self) -> str:
        payload = {
            "phrase": self.phrase,
            "intent": self.intent,
            "source": self.source,
            "added": self.added,
            "version": self.version,
        }
        if self.slots:
            payload["slots"] = self.slots
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


_REQUIRED = ("phrase", "intent", "source", "added")


def parse_entry(line: str, number: int) -> Entry:
    try:
        raw = json.loads(line)
    except json.JSONDecodeError as error:
        raise TableError(f"line {number}: not JSON: {error}") from error
    if not isinstance(raw, dict):
        raise TableError(f"line {number}: not an object")
    for name in _REQUIRED:
        value = raw.get(name)
        if not isinstance(value, str) or not value.strip():
            raise TableError(f"line {number}: field {name!r} is missing or empty")
    slots = raw.get("slots", {})
    if not isinstance(slots, dict) or not all(isinstance(v, str) for v in slots.values()):
        raise TableError(f"line {number}: 'slots' must be an object of strings")
    return Entry(
        phrase=raw["phrase"],
        intent=raw["intent"],
        source=raw["source"],
        added=raw["added"],
        version=str(raw.get("version", "1")),
        slots=dict(slots),
    )


@dataclass(frozen=True)
class Table:
    """Loaded table plus everything needed to reproduce a decision later."""

    entries: tuple[Entry, ...]
    #: sha256 of the file the entries were read from.
    digest: str
    path: str = "<memory>"

    def __post_init__(self) -> None:
        by_key: dict[str, Entry] = {}
        for entry in self.entries:
            previous = by_key.get(entry.key)
            if previous is not None and previous.intent != entry.intent:
                raise TableError(
                    f"phrase {entry.phrase!r} maps to both {previous.intent!r} and {entry.intent!r}"
                )
            by_key[entry.key] = entry
        object.__setattr__(self, "_index", by_key)

    @property
    def index(self) -> dict[str, Entry]:
        return getattr(self, "_index")

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[Entry]:
        return iter(self.entries)

    def provenance(self) -> dict[str, str]:
        """Stamp carried on every match: which table, which rules, which size."""
        return {
            "table_path": self.path,
            "table_digest": self.digest,
            "table_entries": str(len(self.entries)),
            "table_format": TABLE_FORMAT_VERSION,
            "normalizer_version": NORMALIZER_VERSION,
        }


def load_table(path: str | Path) -> Table:
    file = Path(path)
    data = file.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    entries = []
    for number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        entries.append(parse_entry(line, number))
    if not entries:
        raise TableError(f"{file}: table is empty")
    return Table(entries=tuple(entries), digest=digest, path=str(file))


def table_from_entries(entries: Iterable[Entry]) -> Table:
    items = tuple(entries)
    body = "\n".join(entry.to_json() for entry in items).encode("utf-8")
    return Table(entries=items, digest=hashlib.sha256(body).hexdigest())
