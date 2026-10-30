# Troubleshooting

## The app starts but cannot answer

Open **OCI connection** in the sidebar. Check the regional base URL, a supported
model ID or dedicated model endpoint OCID, a Generative AI project OCID, and an OCI
Generative AI API key. The base URL must end in `/openai/v1`, not `/responses`.
A compartment OCID cannot substitute for the project OCID.

Shell environment variables override `.env`. `OCI_MODEL` takes precedence over
`OCI_MODEL_ID`; `OCI_OPENAI_PROJECT` takes precedence over `OCI_GENAI_PROJECT_ID`.

## Compaction has not triggered

Compaction is threshold-based. An enabled request does not necessarily compact.
Keep asking follow-up questions, add a longer starting context, or use the optional
synthetic exchanges. The minimum supported teaching threshold is 1,000 tokens.
A higher threshold can delay compaction; it is not a fix for a format error.

## HTTP 400 / compaction was not applied

Observed deployment errors include:

- `output_text is not supported` or `reasoning_text is not supported`.
- `ValidatorIterator` together with `ResponseOutputTextParam`.

The request adapter addresses visible-text replay. Recognized compaction-format
failures still recover with the original full conversation, without compaction.
The app pauses further compaction attempts to avoid repeating that failure on every
question. Click **Retry compaction next turn**, then submit a question to try again.

An identical retry cannot be expected to fix a repeatable format failure. Reproduce
with a supported model/region and check OCI service compatibility. If reporting the
issue to Oracle, include the error code, model/region, SDK version, minimal sanitized
request shape, and provider request ID if available. Do not include API keys,
encrypted context, private prompts, or the contents of `.env`.

An explicit `/responses/compact` response is not enough to validate the workflow:
continuing with the returned context must also succeed. In local checks, the explicit
endpoint returned an item but continuation still failed validation.

## HTTP 401 or 403

Verify credentials, project access, and model authorization. These errors are not
retried with compaction OFF. Update credentials locally or through the sidebar.

## HTTP 429, 500 or 503

For a temporary failure, wait before retrying manually. The demo does not implement
automatic exponential backoff. For quota exhaustion, check the applicable OCI quota
rather than repeatedly resubmitting. See Oracle's
[API error guidance](https://docs.oracle.com/en-us/iaas/Content/API/References/apierrors.htm).

## Blank or incomplete answer

If the output was cut short, increase **Maximum output tokens per answer** in
**Advanced settings**. The allowance can include reasoning, not only visible text.
Changing this setting starts a new comparison. Incomplete answers are not eligible
for benefit cards.

## Token or speed differences look surprising

- Read the compaction status first. Fallback cannot demonstrate compaction savings.
- Input tokens compare the request histories; total tokens also include output.
- Failed-attempt tokens are unknown, while their time is included.
- The chats generate independent answers, so output length and future histories differ.
- A compaction item returned on one turn can affect the next turn's input.
- Check retained facts and useful answers, not only numbers.

## Proxy or connection errors

`start.sh` unsets proxy variables for its own process. If your environment requires
a proxy, use the manual launch in the README with the correct proxy environment.
If the error persists after updating code, stop the old server with Ctrl+C and
restart it to clear imported modules.

## Port 8501 is in use

Stop the existing app, or run `./start.sh --server.port=8502`.
