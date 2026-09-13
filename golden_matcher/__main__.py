"""CLI: match one phrase or a whole JSONL file of phrases against the table."""

from __future__ import annotations

import argparse
import json
import sys

from .matcher import DEFAULT_THRESHOLD, match
from .table import TableError, load_table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="golden_matcher", description="Deterministic speech matcher")
    parser.add_argument("--table", required=True, help="golden table, JSONL")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("phrase", nargs="*", help="phrase to match, omit to read stdin line by line")
    args = parser.parse_args(argv)

    try:
        table = load_table(args.table)
    except (OSError, TableError) as error:
        print(f"table: {error}", file=sys.stderr)
        return 2

    phrases = [" ".join(args.phrase)] if args.phrase else (line.rstrip("\n") for line in sys.stdin)
    missed = 0
    for phrase in phrases:
        if not phrase.strip():
            continue
        found = match(phrase, table, args.threshold)
        if found is None:
            missed += 1
            print(json.dumps({"phrase": phrase, "intent": None}, ensure_ascii=False))
        else:
            print(json.dumps(found.__dict__, ensure_ascii=False, default=str))
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
