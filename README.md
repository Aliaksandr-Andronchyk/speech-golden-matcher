# speech-golden-matcher

A deterministic matcher that turns a recognised speech phrase into an intent by looking it up
in a golden table. No model, no network, no randomness: the same phrase and the same table
always give the same answer, and every answer says exactly which line of the table produced it.

## Why

Voice features are usually tested against a model that quietly changes under you. For the
commands that must never break – "stop the music", "cancel the alarm" – you want the opposite:
a small table of phrases a human curated, checked in, versioned, and diffable in review. This is
that table plus the matcher that reads it.

What it gives you:

- **A golden table in JSONL**, one entry per line, so git diffs stay readable and merges are sane.
- **Provenance on every match**: which table file, its sha256, which line, where that line came
  from (recording id or ticket), when it was added, and the version of the rules that matched it.
  A decision made today can be explained a year later.
- **Versioned rules**: the normaliser and the matcher carry their own version numbers. Changing a
  normalisation rule changes which key a phrase maps to, so the version must be bumped with it.
- **Refusal over guessing**: below the similarity threshold nothing is returned. A wrong intent in
  a voice assistant is worse than no intent.
- **A table that refuses to load** when a line lacks provenance, or when two phrases normalise to
  the same key but claim different intents.

## How it works

1. **Normalise** (`normalize.py`) – the only place a phrase loses its shape: NFKC, casefold,
   contractions expanded (`what's` becomes `what is`), spoken digits to digits (`seven` to `7`),
   punctuation dropped, fillers (`um`, `uh`) removed. The result is the lookup key.
2. **Exact stage** – key found in the table, confidence `1.0`.
3. **Fuzzy stage** – Jaccard similarity over the normalised words, order free and stable. The
   first entry wins a tie, so file order decides and nothing depends on dict iteration order.
   Below the threshold (default `0.75`) the result is `None`.

## Run it

Python 3.11 or newer, no dependencies.

```bash
# one phrase
python3 -m golden_matcher --table golden.jsonl "Stop the music!"

# a stream of phrases, one per line
printf "um, Call Mum!\nwhat's the weather today\n" | python3 -m golden_matcher --table golden.jsonl
```

Each matched phrase prints one JSON object with the intent, the confidence, the stage and the
full provenance stamp. Unmatched phrases print `{"phrase": ..., "intent": null}`. The exit code
is `0` when everything matched, `1` when something missed, `2` when the table could not be read –
so it drops straight into CI as a regression gate over a file of recorded utterances.

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

21 tests: normalisation rules, table validation and provenance, both matching stages, the
threshold, determinism, and the CLI exit codes.

## The table format

```json
{"added": "2026-09-05", "intent": "call.contact", "phrase": "call mum", "source": "ticket-402", "slots": {"contact": "mum"}, "version": "2"}
```

`phrase`, `intent`, `source` and `added` are required and must be non-empty – a line with no
source is a line nobody can defend later, so the loader rejects the whole file. `slots` and
`version` are optional. Blank lines and lines starting with `#` are ignored.
