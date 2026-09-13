import json
import unittest
from pathlib import Path

from golden_matcher import Entry, TableError, load_table, match, normalize, table_from_entries
from golden_matcher.__main__ import main

TABLE = Path(__file__).resolve().parent.parent / "golden.jsonl"


class NormalizeTest(unittest.TestCase):
    def test_case_punctuation_and_spacing_do_not_matter(self):
        self.assertEqual(normalize("  Stop, the  MUSIC! "), "stop the music")

    def test_spoken_digits_become_digits(self):
        self.assertEqual(normalize("set an alarm for seven"), "set an alarm for 7")

    def test_fillers_are_dropped(self):
        self.assertEqual(normalize("um play some music"), "play some music")

    def test_a_phrase_of_only_fillers_keeps_them(self):
        self.assertEqual(normalize("um uh"), "um uh")

    def test_contractions_are_expanded(self):
        self.assertEqual(normalize("What's the weather today?"), "what is the weather today")

    def test_normalisation_is_stable(self):
        self.assertEqual(normalize("Call Mum."), normalize("call mum"))


class TableTest(unittest.TestCase):
    def test_loads_the_shipped_table(self):
        table = load_table(TABLE)
        self.assertEqual(len(table), 7)
        self.assertEqual(len(table.digest), 64)

    def test_provenance_names_the_table_and_the_rules(self):
        stamp = load_table(TABLE).provenance()
        self.assertEqual(stamp["table_entries"], "7")
        self.assertEqual(stamp["normalizer_version"], "1.1.0")

    def test_a_line_without_source_is_refused(self):
        bad = json.dumps({"phrase": "hi", "intent": "greet", "added": "2026-09-01"})
        path = Path(self.enterContext(__import__("tempfile").TemporaryDirectory())) / "bad.jsonl"
        path.write_text(bad, encoding="utf-8")
        with self.assertRaisesRegex(TableError, "source"):
            load_table(path)

    def test_the_same_phrase_with_two_intents_is_refused(self):
        with self.assertRaisesRegex(TableError, "maps to both"):
            table_from_entries(
                [
                    Entry("call mum", "call.contact", "t-1", "2026-09-01"),
                    Entry("Call mum!", "call.other", "t-2", "2026-09-02"),
                ]
            )


class MatchTest(unittest.TestCase):
    def setUp(self):
        self.table = load_table(TABLE)

    def test_exact_match_is_full_confidence(self):
        found = match("Stop the music!", self.table)
        self.assertEqual(found.intent, "music.stop")
        self.assertEqual(found.confidence, 1.0)
        self.assertEqual(found.stage, "exact")

    def test_slots_come_from_the_table(self):
        self.assertEqual(match("set an alarm for 7", self.table).slots, {"hour": "7"})

    def test_close_phrase_matches_fuzzily(self):
        found = match("please play some music", self.table)
        self.assertEqual(found.intent, "music.play")
        self.assertEqual(found.stage, "fuzzy")
        self.assertLess(found.confidence, 1.0)

    def test_unrelated_phrase_matches_nothing(self):
        self.assertIsNone(match("open the garage door", self.table))

    def test_threshold_is_respected(self):
        self.assertIsNone(match("please play some music", self.table, threshold=0.99))

    def test_match_carries_provenance_of_the_golden_line(self):
        found = match("cancel the alarm", self.table)
        self.assertEqual(found.provenance["entry_source"], "session-114/utt-9")
        self.assertEqual(found.provenance["table_digest"], self.table.digest)

    def test_a_contraction_reaches_the_spelled_out_golden_line(self):
        found = match("what's the weather today", self.table)
        self.assertEqual(found.intent, "weather.today")
        self.assertEqual(found.stage, "exact")

    def test_the_same_input_gives_the_same_output(self):
        first = match("what's the weather today", self.table)
        second = match("what's the weather today", self.table)
        self.assertIsNotNone(first)
        self.assertEqual(first, second)


class CliTest(unittest.TestCase):
    def test_exit_code_zero_when_everything_matched(self):
        self.assertEqual(main(["--table", str(TABLE), "stop", "the", "music"]), 0)

    def test_exit_code_one_when_something_missed(self):
        self.assertEqual(main(["--table", str(TABLE), "open", "the", "garage"]), 1)

    def test_missing_table_is_reported(self):
        self.assertEqual(main(["--table", "no-such-file.jsonl", "hi"]), 2)


if __name__ == "__main__":
    unittest.main()
