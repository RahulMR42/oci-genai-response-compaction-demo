"""Independent OCI chat histories and measurements for paired conversations."""
from copy import deepcopy
from time import perf_counter

from compaction_demo import next_history, oci_input, output_items
from ui_demo import is_compaction_compatibility_error


def new_branch(seed):
    return {"history": deepcopy(seed), "full_history": deepcopy(seed), "paused": False}


def safe_error(error):
    status = getattr(error, "status_code", None)
    if status in (401, 403):
        return "OCI denied access. Check the API key and project/model permissions."
    if status == 429:
        return "OCI rate or quota limit reached. Wait before sending another question."
    if status == 400:
        return "OCI rejected the request. Check model compatibility, context size and settings."
    if status:
        return f"OCI request failed (HTTP {status}). Try again later."
    return "Could not complete the OCI request. Check the endpoint and connection."


def chat_turn(client, model, branch, prompt, enabled, threshold, max_output_tokens=1024):
    """Return a new state and measured result; never modify a caller's history."""
    state = deepcopy(branch)
    user = {"role": "user", "content": prompt}
    history = state["history"] + [user]
    full_history = state["full_history"] + [user]
    active = enabled and not state["paused"]
    notices = []
    attempts = []
    started = perf_counter()
    if enabled and state["paused"]:
        notices.append("Compaction is paused after an OCI format error. Using full history. "
                       "Use Retry compaction next turn to test it again.")
        history = full_history

    def create(items, compact):
        settings = {"extra_body": {"context_management": [
            {"type": "compaction", "compact_threshold": threshold}]}} if compact else {}
        attempt = {"compaction_requested": compact}
        begin = perf_counter()
        try:
            response = client.responses.create(model=model, input=oci_input(items),
                store=False, max_output_tokens=max_output_tokens, **settings)
            attempt["status"] = "success"
            return response
        except Exception as error:
            attempt["status"] = "failed"
            attempt["http_status"] = getattr(error, "status_code", None)
            raise
        finally:
            attempt["seconds"] = round(perf_counter() - begin, 3)
            attempts.append(attempt)

    error_text = None
    response = None
    try:
        try:
            response = create(history, active)
        except Exception as error:
            has_compaction = any(item.get("type") == "compaction" for item in history)
            if not enabled or not (active or has_compaction) or not is_compaction_compatibility_error(error):
                raise
            active = False
            state["paused"] = True
            history = full_history
            notices.append("OCI rejected compaction. Recovered with full history and compaction OFF. "
                           "Compaction is paused until you retry it.")
            response = create(history, False)
    except Exception as error:
        error_text = safe_error(error)

    elapsed = round(perf_counter() - started, 3)
    output = output_items(response) if response is not None else []
    observed = any(item.get("type") == "compaction" for item in output)
    used_compacted = response is not None and any(item.get("type") == "compaction" for item in history)
    state["history"] = next_history(history, output) if response is not None else history
    state["full_history"] = full_history + [item for item in output if item.get("type") != "compaction"]
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    result = {
        "answer": getattr(response, "output_text", "") if response is not None else "",
        "error": error_text, "notices": notices, "seconds": elapsed,
        "input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens,
        "attempts": attempts, "enabled": enabled, "effective_enabled": active and response is not None,
        "compaction_observed": observed, "used_compacted_context": used_compacted,
        "history_items": len(oci_input(state["history"])),
        "full_history_items": len(oci_input(state["full_history"])),
        "output_types": [item.get("type", "unknown") for item in output],
        "incomplete": getattr(response, "status", None) == "incomplete",
    }
    return state, result
