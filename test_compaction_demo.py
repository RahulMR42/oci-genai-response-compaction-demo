"""Offline checks for the history rules and API request sequence."""

import contextlib
import io
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from compaction_demo import automatic_demo, explicit_demo, next_history, oci_input


def result(items):
    output = []
    for item in items:
        entry = Mock()
        entry.model_dump.return_value = deepcopy(item)
        output.append(entry)
    return SimpleNamespace(output=output, output_text="An illustrative answer")


class HistoryTests(unittest.TestCase):
    def test_no_compaction_keeps_old_history_and_every_output_item(self):
        history = [{"role": "user", "content": "remember this"}]
        output = [{"type": "reasoning", "id": "r"}, {"type": "message", "id": "m"}]
        self.assertEqual(next_history(history, output), history + output)

    def test_latest_compaction_keeps_encrypted_fields_and_all_later_items(self):
        output = [
            {"type": "compaction", "encrypted_content": "old"},
            {"type": "message", "id": "before"},
            {"type": "compaction", "encrypted_content": "opaque", "id": "c"},
            {"type": "reasoning", "id": "r"},
            {"type": "message", "id": "after"},
        ]
        self.assertEqual(next_history([{"role": "user"}], output), output[2:])

    def test_empty_output_preserves_history(self):
        history = [{"role": "user", "content": "keep me"}]
        self.assertEqual(next_history(history, []), history)

    def test_oci_input_adapts_text_without_changing_stored_output(self):
        items = [
            {"type": "reasoning", "content": [{"type": "reasoning_text", "text": "private"}]},
            {"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": "Budget is 150 USD"}]},
            {"type": "compaction", "encrypted_content": "opaque", "id": "c"},
            {"type": "reasoning", "encrypted_content": "encrypted", "content": []},
            {"type": "function_call", "call_id": "call", "arguments": "{}"},
        ]
        original = deepcopy(items)
        self.assertEqual(oci_input(items), [
            {"role": "assistant", "content": "Budget is 150 USD"}, *items[2:]])
        self.assertEqual(items, original)

    def run_flow(self, demo, first_output, compact_output=None):
        client = SimpleNamespace(responses=Mock())
        requests = []
        responses = iter([result(first_output), result([])])

        def create(**kwargs):
            requests.append(deepcopy(kwargs))
            return next(responses)

        client.responses.create.side_effect = create
        if compact_output is not None:
            client.responses.compact.return_value = result(compact_output)
        with contextlib.redirect_stdout(io.StringIO()):
            demo(client, "test-model")
        self.assertTrue(all(r["store"] is False for r in requests))
        return client, requests

    def test_explicit_replays_whole_compacted_output(self):
        compacted = [
            {"type": "message", "id": "retained"},
            {"type": "compaction", "encrypted_content": "opaque"},
        ]
        client, requests = self.run_flow(
            explicit_demo, [{"type": "reasoning", "id": "r"}], compacted,
        )
        self.assertEqual(requests[1]["input"][:-1], compacted)
        compact_request = client.responses.compact.call_args.kwargs
        self.assertEqual(compact_request["input"][-1]["type"], "reasoning")
        self.assertNotIn("store", compact_request)

    def test_automatic_continues_from_compaction(self):
        output = [{"type": "message", "id": "before"},
                  {"type": "compaction", "encrypted_content": "opaque"},
                  {"type": "message", "id": "after"}]
        client, requests = self.run_flow(automatic_demo, output)
        self.assertEqual(requests[1]["input"][:-1], output[1:])
        self.assertEqual(requests[0]["extra_body"], requests[1]["extra_body"])
        client.responses.compact.assert_not_called()

    def test_automatic_no_compaction_continues_full_history(self):
        output = [{"type": "message", "id": "answer"}]
        _, requests = self.run_flow(automatic_demo, output)
        self.assertEqual(requests[1]["input"][:-1], requests[0]["input"] + output)


if __name__ == "__main__":
    unittest.main()
