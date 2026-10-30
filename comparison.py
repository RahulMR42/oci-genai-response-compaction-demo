"""Plain-language, evidence-gated comparison of two measured chat answers."""

def change(before, after, unit=None):
    if before is None or after is None:
        return "Not reported"
    if unit == "seconds":
        difference = before - after
        if abs(difference) < 0.01:
            return "About the same"
        return f"{abs(difference):.2f} s {'faster' if difference > 0 else 'slower'}"
    if before == 0:
        return "Same" if after == 0 else "More tokens"
    percent = (before - after) / before * 100
    if abs(percent) < 0.1:
        return "About the same"
    return f"{abs(percent):.1f}% {'fewer' if percent > 0 else 'more'}"


def compare_answers(off, on):
    if off.get("error") or on.get("error"):
        status, message = "error", "One answer failed. There is no complete comparison for this question."
    elif off.get("incomplete") or on.get("incomplete"):
        status, message = "incomplete", "An answer was cut short. Compare complete answers before judging the benefit."
    elif not on.get("effective_enabled"):
        status, message = "fallback", "Compaction was not applied. Both chats used full history, so no compaction benefit was measured."
    elif on.get("used_compacted_context"):
        status, message = "used", "Compaction was used for this answer. Here is the measured difference."
    elif on.get("compaction_observed"):
        status, message = "ready", "History was compacted. Ask another question to measure the effect of using it."
    else:
        status, message = "waiting", "Compaction has not triggered yet. Keep chatting to build up enough history."
    eligible = status == "used"
    return {"status": status, "message": message, "eligible": eligible,
            "input": change(off.get("input_tokens"), on.get("input_tokens")) if eligible else "Not measured",
            "total": change(off.get("total_tokens"), on.get("total_tokens")) if eligible else "Not measured",
            "time": change(off.get("seconds"), on.get("seconds"), "seconds") if eligible else "Not measured"}
