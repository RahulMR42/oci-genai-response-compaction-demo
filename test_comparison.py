"""Comparison claims must match measured usage and successful compaction."""
from copy import deepcopy
from unittest import TestCase

from comparison import change, compare_answers


class ComparisonTests(TestCase):
    def setUp(self):
        self.off = {"input_tokens": 1000, "total_tokens": 1200, "seconds": 4.0,
                    "effective_enabled": False, "error": None, "incomplete": False,
                    "used_compacted_context": False, "compaction_observed": False}
        self.on = dict(self.off, input_tokens=400, total_tokens=600, seconds=3.0,
                       effective_enabled=True, used_compacted_context=True)

    def test_actual_compacted_answer_shows_measured_reductions(self):
        result = compare_answers(self.off, self.on)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["input"], "60.0% fewer")
        self.assertEqual(result["total"], "50.0% fewer")
        self.assertEqual(result["time"], "1.00 s faster")

    def test_fallback_cannot_claim_savings_despite_lower_numbers(self):
        self.on["effective_enabled"] = False
        result = compare_answers(self.off, self.on)
        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["input"], "Not measured")

    def test_returned_compaction_is_not_yet_evidence_of_savings(self):
        self.on.update(used_compacted_context=False, compaction_observed=True)
        result = compare_answers(self.off, self.on)
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["eligible"])

    def test_failed_or_incomplete_answers_cannot_claim_benefits(self):
        for key, value in [("error", "failed"), ("incomplete", True)]:
            with self.subTest(key=key):
                on = dict(self.on, **{key: value})
                self.assertFalse(compare_answers(self.off, on)["eligible"])

    def test_higher_usage_and_slower_time_are_reported_as_regressions(self):
        self.on.update(input_tokens=1500, total_tokens=1800, seconds=6.0)
        result = compare_answers(self.off, self.on)
        self.assertEqual(result["input"], "50.0% more")
        self.assertEqual(result["time"], "2.00 s slower")

    def test_missing_usage_and_zero_baseline_do_not_create_percentages(self):
        self.assertEqual(change(None, 100), "Not reported")
        self.assertEqual(change(0, 100), "More tokens")
        self.assertEqual(change(0, 0), "Same")
