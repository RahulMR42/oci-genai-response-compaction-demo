"""Recovery checks for live OCI request failures."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from ui_demo import build_history, execute_flow
from test_compaction_demo import result


class ProviderError(Exception):
    def __init__(self, status, message):
        self.status_code = status
        self.body = {"message": message}


class LiveFlowTests(unittest.TestCase):
    def run_flow(self, responses, enabled=True):
        requests = []
        pending = iter(responses)
        def create(**kwargs):
            requests.append(deepcopy(kwargs))
            response = next(pending)
            if isinstance(response, Exception):
                raise response
            return response
        client = SimpleNamespace(responses=Mock())
        client.responses.create.side_effect = create
        value = execute_flow(client, "model", "budget 150; vegetarian; peanut allergy",
                             "Recall preferences", 2, enabled, 1000)
        return value, requests

    def test_initial_compaction_error_recovers_without_compaction(self):
        error = ProviderError(400, "output_text is not supported by model")
        first = result([
            {"type": "reasoning", "content": [{"type": "reasoning_text", "text": "internal"}]},
            {"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": "Preferences recorded"}]},
        ])
        value, calls = self.run_flow([error, first, result([])])
        self.assertTrue(value["enabled"])
        self.assertFalse(value["effective_enabled"])
        self.assertEqual(len(value["notices"]), 1)
        self.assertEqual(calls[0]["input"], calls[1]["input"])
        self.assertIn("extra_body", calls[0])
        self.assertNotIn("extra_body", calls[1])
        self.assertNotIn("extra_body", calls[2])
        self.assertEqual(calls[2]["input"][-2],
                         {"role": "assistant", "content": "Preferences recorded"})

    def test_follow_up_compaction_error_restores_original_history(self):
        compacted = {"type": "compaction", "encrypted_content": "opaque"}
        error = ProviderError(400, "ValidatorIterator ResponseOutputTextParam")
        value, calls = self.run_flow([result([compacted]), error, result([])])
        self.assertFalse(value["effective_enabled"])
        self.assertTrue(value["compaction_observed"])
        self.assertEqual(calls[1]["input"][0], compacted)
        self.assertEqual(calls[2]["input"][:-1], calls[0]["input"])
        self.assertNotIn("extra_body", calls[2])
        self.assertEqual(compacted["encrypted_content"], "opaque")

    def test_unrelated_errors_are_not_recovered(self):
        for status, message in [(401, "output_text is not supported"),
                                (429, "quota"), (400, "invalid model")]:
            with self.subTest(status=status), self.assertRaises(ProviderError):
                self.run_flow([ProviderError(status, message)])

    def test_off_does_not_retry_format_errors(self):
        with self.assertRaises(ProviderError):
            self.run_flow([ProviderError(400, "reasoning_text is not supported")], enabled=False)

    def test_successful_compaction_remains_enabled(self):
        value, calls = self.run_flow([
            result([{"type": "compaction", "encrypted_content": "opaque"}]), result([])])
        self.assertTrue(value["effective_enabled"])
        self.assertEqual(value["notices"], [])
        self.assertEqual(len(calls), 2)
        self.assertIn("extra_body", calls[1])


if __name__ == "__main__":
    unittest.main()
