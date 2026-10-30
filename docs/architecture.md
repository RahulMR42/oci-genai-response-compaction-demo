# Architecture and measurement rules

## One prompt, two histories

`app.py` sends each question to two independent branches via `chat_flow.chat_turn`.
Both begin with the same starting context. The OFF branch uses the full history;
the ON branch adds `context_management` with the chosen compaction threshold.
Both use the same model, project, answer limit, and `store=False`.

```text
                         shared question
                         /             \
                full-history chat    compaction chat
                         |             |
                    OCI response   OCI response
                         \             /
                     latest comparison
```

Calls are sequential, with alternating order. Each branch retains its own generated
answers; histories can therefore diverge even when every user question is identical.
The UI is designed for exploring behavior rather than attributing causality.

## History retention

Each branch keeps two copies in Streamlit session state:

- `history`: context to send on the next turn, potentially beginning with an opaque compaction item.
- `full_history`: the original messages and returned non-compaction output, retained for recovery.

When automatic compaction returns an item, `next_history` keeps the newest
compaction item and all subsequent output. Without a new item, it appends all output
to the existing history. The full-history copy excludes compaction items and keeps
the original conversation available for fallback.

`output_items` preserves serialized output. At the OCI request boundary, `oci_input`
converts assistant messages containing only `output_text` blocks into plain assistant
text and omits unencrypted reasoning content. This works around observed gpt-oss
replay errors. Encrypted reasoning, compaction items, and tool items are preserved.
It is a compatibility adapter, not a general-purpose SDK implementation.

The CLI explicit example replaces its history with the complete `responses.compact`
output, then adds the next question. Compaction content is never decrypted or edited.

## Compatibility recovery

For recognized HTTP 400 text-format errors on the compaction branch:

1. Retain the complete original conversation.
2. Retry once with full history and no compaction options.
3. Mark the result as a fallback and pause compaction on subsequent questions.
4. Allow the user to resume attempts with **Retry compaction next turn**.

The retry control only affects the next submitted question. It does not replay an
old answer. Errors such as invalid credentials, rate limits, or unrelated validation
failures are surfaced without this compatibility retry. SDK retries are disabled;
there is no hidden transient-error retry loop.

## Measurements

`chat_turn` measures elapsed time with `perf_counter`. Each attempt records duration,
success/failure, and HTTP status when available. The per-answer duration covers all
attempts including fallback. It excludes time spent waiting for the other branch,
UI rendering, and the user's reading time. Responses are not streamed, so this is
complete-response latency rather than time to first token.

Token counts come from the successful response's `usage`. If OCI omits them, the UI
shows a dash. Total tokens use OCI's total when available, otherwise input plus output.
Failed-attempt usage is unknown and is not estimated or added. No tokenization of
encrypted context or cost conversion is performed.

## Benefit eligibility

`comparison.compare_answers` only displays percentage/time differences when:

- Both answers succeeded and are complete.
- The ON branch stayed enabled for the successful request.
- That request actually carried a previously returned compaction item.

A newly returned item is labeled ready for the next question. Fallback, failed,
incomplete, and not-yet-compacted runs do not receive benefit cards. More tokens or
slower time are reported as regressions rather than hidden. Missing counts and
zero baselines do not create unsupported percentages.

For nonzero baselines, the token percentage is `(OFF - ON) / OFF * 100`. Positive
values become “fewer”; negative values become “more.” Time uses `OFF - ON` seconds,
rendered as faster/slower. These compare the two runs; they do not isolate compaction
from independent answer lengths, caching, network variation, or service load.

## Session lifetime and data

Conversation histories and measurements are held in the running Streamlit session;
there is no application database or durable chat-save feature. Starting a new
conversation or changing connection/context/token settings resets both histories.
CSV download contains measurements rather than the conversation text.

Prompts and history are sent to the configured OCI endpoint. The launcher binds to
localhost. Keep local credentials and downloaded measurements out of Git; this demo
does not supply authentication or access controls for shared hosting.
