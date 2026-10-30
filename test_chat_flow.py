"""State, usage and failure checks for the paired chatbot."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from chat_flow import chat_turn, new_branch
from test_compaction_demo import result
from test_ui_demo import ProviderError


def answer(text="Recorded", compact=False, tokens=(120, 30)):
    items = [{"type": "reasoning", "content": [{"type": "reasoning_text", "text": "private"}]},
             {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}]
    if compact:
        items.insert(0, {"type": "compaction", "encrypted_content": "opaque"})
    response = result(items)
    response.output_text = text
    response.usage = SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1], total_tokens=sum(tokens))
    response.status = "completed"
    return response


class ChatTests(TestCase):
    def client(self, *responses):
        client = SimpleNamespace(responses=Mock())
        client.responses.create.side_effect = responses
        return client

    def test_compaction_carries_opaque_context_to_next_question(self):
        seed = [{"role": "user", "content": "budget 150"}]
        initial = new_branch(seed)
        untouched = deepcopy(initial)
        client = self.client(answer(compact=True), answer("150"))
        state, first = chat_turn(client, "model", initial, "Remember", True, 1000)
        state, second = chat_turn(client, "model", state, "Budget?", True, 1000)
        self.assertEqual(initial, untouched)
        self.assertTrue(first["compaction_observed"])
        self.assertFalse(first["used_compacted_context"])
        self.assertTrue(second["used_compacted_context"])
        sent = client.responses.create.call_args.kwargs["input"]
        self.assertEqual(sent[0], {"type": "compaction", "encrypted_content": "opaque"})
        self.assertEqual(sent[-1]["content"], "Budget?")
        self.assertEqual(state["full_history"][0], seed[0])
        self.assertFalse(any(i.get("type") == "compaction" for i in state["full_history"]))

    def test_fallback_restores_full_context_and_pauses_future_compaction(self):
        state = new_branch([{"role": "user", "content": "budget 150"}])
        state["history"] = [{"type": "compaction", "encrypted_content": "opaque"}]
        error = ProviderError(400, "ValidatorIterator ResponseOutputTextParam")
        client = self.client(error, answer("150"), answer("vegetarian"))
        with patch("chat_flow.perf_counter", side_effect=[0, 0, 2, 2, 5, 5]):
            state, first = chat_turn(client, "model", state, "Budget?", True, 1000)
        self.assertTrue(state["paused"])
        self.assertFalse(first["effective_enabled"])
        self.assertFalse(first["used_compacted_context"])
        self.assertEqual(first["seconds"], 5)
        self.assertEqual(first["total_tokens"], 150)
        self.assertEqual(len(first["attempts"]), 2)
        retry = client.responses.create.call_args.kwargs
        self.assertEqual(retry["input"][0]["content"], "budget 150")
        self.assertNotIn("extra_body", retry)
        state, second = chat_turn(client, "model", state, "Food?", True, 1000)
        self.assertEqual(len(second["attempts"]), 1)
        self.assertNotIn("extra_body", client.responses.create.call_args.kwargs)
        self.assertTrue(second["notices"])

    def test_manual_retry_can_resume_compaction(self):
        state = new_branch([])
        state["paused"] = True
        state["paused"] = False  # Sidebar retry action.
        client = self.client(answer(compact=True))
        state, value = chat_turn(client, "model", state, "Question", True, 1000)
        self.assertTrue(value["effective_enabled"])
        self.assertIn("extra_body", client.responses.create.call_args.kwargs)

    def test_unrelated_failure_keeps_question_and_does_not_invent_usage(self):
        state = new_branch([])
        client = self.client(ProviderError(401, "SECRET provider body"))
        state, value = chat_turn(client, "model", state, "Remember allergy", True, 1000)
        self.assertEqual(len(value["attempts"]), 1)
        self.assertIsNone(value["input_tokens"])
        self.assertIsNone(value["total_tokens"])
        self.assertNotIn("SECRET", value["error"])
        self.assertEqual(state["history"][-1]["content"], "Remember allergy")
        self.assertFalse(state["paused"])

    def test_off_and_on_keep_independent_histories(self):
        off, on = new_branch([]), new_branch([])
        client = self.client(answer("OFF answer"), answer("ON answer", compact=True))
        off, _ = chat_turn(client, "model", off, "Same question", False, 1000)
        on, _ = chat_turn(client, "model", on, "Same question", True, 1000)
        requests = client.responses.create.call_args_list
        self.assertEqual(requests[0].kwargs["input"], requests[1].kwargs["input"])
        self.assertNotIn("extra_body", requests[0].kwargs)
        self.assertIn("extra_body", requests[1].kwargs)
        self.assertFalse(any(i.get("type") == "compaction" for i in off["history"]))
        self.assertEqual(on["history"][0]["encrypted_content"], "opaque")
