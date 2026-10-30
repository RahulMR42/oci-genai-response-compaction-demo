"""A small OCI Responses API example: remember, compact, ask again."""

import argparse
import os
from getpass import getpass


TRIP = (
    "Help plan my Kyoto trip. We are two adults, travelling November 12-16. "
    "Our hotel budget is 150 USD per night. We need vegetarian food, "
    "and one traveller has a peanut allergy. Acknowledge these preferences briefly."
)
QUESTION = "What is our hotel budget, and which food restrictions must you remember?"
EXPECTED = "150 USD/night; vegetarian food; peanut allergy"


def output_items(result):
    # Preserve every serialized field, including opaque encrypted context.
    return [item.model_dump(mode="json", exclude_none=True) for item in result.output]


def oci_input(items):
    """Adapt visible text for OCI gpt-oss input; preserve opaque context and tools.

    OCI currently rejects output_text and reasoning_text on replay. Keep the
    original output in application history, but send assistant text as a message
    and omit unencrypted reasoning at the request boundary.
    """
    adapted = []
    for item in items:
        if (item.get("type") == "reasoning" and item.get("content")
                and not item.get("encrypted_content")):
            continue
        content = item.get("content")
        if (item.get("role") == "assistant" and isinstance(content, list)
                and content and all(part.get("type") == "output_text" for part in content)):
            adapted.append({"role": "assistant", "content": "\n".join(
                part["text"] for part in content)})
        else:
            adapted.append(item)
    return adapted


def next_history(history, output):
    """Automatic mode: start at the newest compaction, or keep prior history."""
    for index in range(len(output) - 1, -1, -1):
        if output[index].get("type") == "compaction":
            return output[index:]
    return history + output


def show_compaction(output):
    observed = any(item.get("type") == "compaction" for item in output)
    print("Compaction returned:", observed)
    if not observed:
        print("No compaction item returned; automatic mode keeps the existing history.")
    return observed


def explicit_demo(client, model):
    print("1. Tell the assistant our travel preferences.")
    history = [{"role": "user", "content": TRIP}]
    response = client.responses.create(model=model, input=oci_input(history), store=False)
    print(response.output_text)
    history += output_items(response)

    print("\n2. Ask OCI to compact this history now (one additional API call).")
    compacted = client.responses.compact(model=model, input=oci_input(history))
    # Explicit mode: replace history with the ENTIRE returned output array.
    history = output_items(compacted)
    if not show_compaction(history):
        raise RuntimeError("Explicit compaction returned no compaction item.")

    print("\n3. Ask a follow-up using the returned context.")
    history.append({"role": "user", "content": QUESTION})
    response = client.responses.create(model=model, input=oci_input(history), store=False)
    print(response.output_text)
    print("\nCheck the answer against:", EXPECTED)


def automatic_demo(client, model):
    settings = {"context_management": [{"type": "compaction", "compact_threshold": 1000}]}
    print("1. Build a longer travel conversation locally (no API calls yet).")
    history = [{"role": "user", "content": TRIP}]
    # Synthetic exchanges help this teaching example exceed the demo threshold.
    for day in range(1, 41):
        history += [
            {"role": "user", "content": (
                f"Planning update {day}: compare gardens, temples, and train routes. "
                "Prefer relaxed mornings and allow time for lunch and rest. "
                "Keep our original budget and food restrictions unchanged."
            )},
            {"role": "assistant", "content": (
                f"Update {day} noted. I will compare those activities and allow "
                "time for breaks while keeping the original preferences."
            )},
        ]
    history.append({"role": "user", "content": "Summarize our trip preferences briefly."})

    print("\n2. Send it with automatic compaction enabled at 1,000 tokens.")
    response = client.responses.create(
        model=model, input=oci_input(history), store=False, extra_body=settings,
    )
    print(response.output_text)
    output = output_items(response)
    show_compaction(output)
    history = next_history(history, output)

    print("\n3. Ask a follow-up with the updated history and the same settings.")
    history.append({"role": "user", "content": QUESTION})
    response = client.responses.create(
        model=model, input=oci_input(history), store=False, extra_body=settings,
    )
    print(response.output_text)
    # Repeat this update after EVERY response in a longer conversation.
    history = next_history(history, output_items(response))
    print("\nCheck the answer against:", EXPECTED)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("explicit", "automatic"))
    args = parser.parse_args()

    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()  # Existing shell variables take precedence over .env.
    model = os.getenv("OCI_MODEL") or os.getenv("OCI_MODEL_ID")
    project = os.getenv("OCI_OPENAI_PROJECT") or os.getenv("OCI_GENAI_PROJECT_ID")
    base_url = os.getenv("OCI_BASE_URL")
    if not base_url and os.getenv("OCI_REGION"):
        base_url = (
            f"https://inference.generativeai.{os.environ['OCI_REGION']}"
            ".oci.oraclecloud.com/openai/v1"
        )
    if not all((model, project, base_url)):
        parser.error("Set OCI_MODEL_ID, OCI_GENAI_PROJECT_ID, and OCI_REGION (or OCI_BASE_URL).")
    if not base_url.rstrip("/").endswith("/openai/v1"):
        parser.error("OCI_BASE_URL must end in /openai/v1.")
    key = os.getenv("OCI_GENAI_API_KEY") or getpass("OCI Generative AI API key: ")
    with OpenAI(api_key=key, base_url=base_url, project=project) as client:
        demo = explicit_demo if args.mode == "explicit" else automatic_demo
        demo(client, model)


if __name__ == "__main__":
    main()
