"""Request building and reporting shared by the Streamlit UI and offline checks."""
from compaction_demo import next_history, output_items, oci_input


def build_history(preferences, exchanges):
    history = [{"role": "user", "content": preferences}]
    for number in range(1, exchanges + 1):
        history.extend([
            {"role": "user", "content": (
                f"Planning update {number}: compare gardens, temples, and train routes. "
                "Prefer relaxed mornings and allow time for lunch and rest. "
                "Keep our original budget and food restrictions unchanged."
            )},
            {"role": "assistant", "content": (
                f"Update {number} noted. I will compare activities and include breaks "
                "while preserving the original preferences."
            )},
        ])
    history.append({"role": "user", "content": "Summarize our trip preferences briefly."})
    return history


def request_options(enabled, threshold):
    if not enabled:
        return {}
    return {"extra_body": {"context_management": [
        {"type": "compaction", "compact_threshold": threshold}
    ]}}


def request_code(enabled, threshold):
    return (
        'from ui_demo import execute_flow\n\n'
        '# Live OCI client, model and conversation come from Run settings.\n'
        '# execute_flow normalizes OCI history content before each request.\n'
        f'result = execute_flow(\n'
        '    client, model, preferences, question, exchanges,\n'
        f'    enabled={enabled!r}, threshold={threshold},\n'
        ')\n'
        '# ON adds context_management to both requests:\n'
        f'# {{"type": "compaction", "compact_threshold": {threshold}}}\n'
        '# Known OCI compaction format errors retry once with full history.\n'
        '# Inspect notices and effective_enabled to see if recovery occurred.\n'
        'print(result["answer"])\n'
        'print(result["notices"])\n'
    )


def is_compaction_compatibility_error(error):
    """Only recover from observed OCI format failures, never auth/quota errors."""
    if getattr(error, "status_code", None) != 400:
        return False
    body = getattr(error, "body", None)
    if not isinstance(body, dict):
        return False
    message = body.get("message", "")
    return ("output_text is not supported" in message
            or "reasoning_text is not supported" in message
            or ("ValidatorIterator" in message and "ResponseOutputTextParam" in message))


def execute_flow(client, model, preferences, question, exchanges, enabled, threshold):
    original_history = build_history(preferences, exchanges)
    original_items = len(original_history)
    effective_enabled = enabled
    notices = []
    options = request_options(enabled, threshold)

    def create(history, settings):
        return client.responses.create(model=model, input=oci_input(history),
                                       store=False, **settings)

    def recovery_notice(stage):
        notices.append(
            f"OCI rejected compaction during the {stage}. Retried with the full "
            "conversation and compaction OFF. This answer is from Live OCI; "
            "compaction was not applied to the follow-up. Recovery adds a request; "
            "usage below includes successful responses only.")

    try:
        first = create(original_history, options)
    except Exception as error:
        if not enabled or not is_compaction_compatibility_error(error):
            raise
        effective_enabled = False
        options = {}
        recovery_notice("initial request")
        first = create(original_history, options)

    output = output_items(first)
    history = (next_history(original_history, output) if effective_enabled
               else original_history + output)
    retained_items = len(history)
    follow_history = history + [{"role": "user", "content": question}]
    try:
        follow_up = create(follow_history, options)
    except Exception as error:
        if not effective_enabled or not is_compaction_compatibility_error(error):
            raise
        # We still have the full original conversation. Never alter or decrypt a
        # compaction item; rebuild from that original history for this retry.
        effective_enabled = False
        recovery_notice("follow-up request")
        history = original_history + [item for item in output
                                      if item.get("type") != "compaction"]
        retained_items = len(history)
        follow_up = create(history + [{"role": "user", "content": question}], {})

    follow_output = output_items(follow_up)
    usage = []
    for label, response in [("Initial answer", first), ("Follow-up", follow_up)]:
        value = getattr(response, "usage", None)
        usage.append({"request": label, "input_tokens": getattr(value, "input_tokens", None),
                      "output_tokens": getattr(value, "output_tokens", None)})
    return {
        "enabled": enabled, "effective_enabled": effective_enabled, "notices": notices,
        "initial_answer": first.output_text,
        "answer": follow_up.output_text, "usage": usage,
        "compaction_observed": any(x.get("type") == "compaction" for x in output + follow_output),
        "first_output_types": [x.get("type", "unknown") for x in output],
        "follow_up_output_types": [x.get("type", "unknown") for x in follow_output],
        "original_items": original_items, "retained_items": retained_items,
    }
