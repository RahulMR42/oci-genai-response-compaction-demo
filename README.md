# OCI Generative AI Compaction Chat

A live Streamlit chatbot that compares **full conversation history** with **automatic
compaction**, side by side, using the OCI Responses API. Ask one question and get
two independent model answers, with a simple comparison of tokens and response time.

The app answers **“Did compaction help on this question?”** It only highlights
measured reductions or increases when a complete answer actually used compacted
context. If OCI rejects compaction, the app reports the fallback instead of
presenting the result as a compaction benefit.

## What you can compare

| Without compaction | With compaction |
| --- | --- |
| Sends the full conversation on each question. | Requests automatic compaction at your token threshold. |
| Keeps its own answers and history. | Keeps its own answers and returned compacted context. |
| Shows reported input/total tokens and complete request time. | Shows the same measurements, including time spent recovering from errors. |

The latest answers appear side by side. A three-row table compares input tokens,
total tokens, and answer time. When eligible, cards show percentages fewer/more
and seconds faster/slower. Earlier questions, trend charts, totals, request attempts,
and CSV export are available in expanders.

**This is an exploratory demo, not a controlled benchmark.** Answers and histories
diverge, response lengths vary, and service load affects timing. Compaction can lose
details and does not guarantee token, cost, or latency savings.

## Requirements

- Python **3.11+** for the UI and current dependency versions. Local validation used Python 3.13.
- An OCI Generative AI API key with access to your model and project.
- A **Generative AI project OCID**, not a compartment OCID.
- A Responses-compatible model or dedicated model endpoint in a supported OCI region.

OCI access is required for every chat answer. There is no preview or simulated mode.
The app normally makes two live requests per question; recovery can add a request.

## Quick start

```bash
git clone https://github.com/RahulMR42/oci-genai-response-compaction-demo.git
cd oci-genai-response-compaction-demo
cp -n .env.example .env
```

Edit `.env` with your region, model and project. Set `OCI_GENAI_API_KEY` locally, or
enter it in the UI's **OCI connection** section. Keep `.env` out of Git.

```bash
./start.sh
```

Open **http://127.0.0.1:8501**. The launcher creates `.venv`, installs dependencies
when `requirements.txt` changes, disables proxy variables for its process, and binds
to localhost. Stop it with **Ctrl+C**. For another port:

```bash
./start.sh --server.port=8502
```

Manual setup, or an environment that requires a proxy:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true --browser.gatherUsageStats=false
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell and use the
manual setup. The shell launcher is intended for macOS/Linux or WSL.

## Try the comparison

1. Open the app. Both chats start with the same editable Kyoto trip facts:
   **150 USD/night, vegetarian meals, and a peanut allergy**.
2. Ask: **“Plan a relaxed first day in Kyoto.”**
3. Ask follow-ups such as **“Suggest a suitable lunch”** and
   **“What budget and food restrictions must you remember?”**
4. Read the status above the latest answers before interpreting the numbers.
5. Check that important facts survived, as well as checking tokens and speed.

Under **Starting context**, change the facts for another topic, or add optional
synthetic travel exchanges to reach the threshold sooner. The default is zero.
Under **Advanced settings**, adjust the compaction threshold (minimum 1,000 tokens)
and answer token limit. Choose a threshold below your model's context limit with
room for answers.

**New conversation** clears both histories. Changes to the connection, model,
starting context, or token settings also reset both sides. **Retry compaction next
turn** resumes compaction attempts after a compatibility fallback; it does not resend
the previous question.

## Understand the result

| Status | What it means |
| --- | --- |
| Compaction has not triggered | The request allowed compaction, but no compaction item was returned. Keep chatting. |
| History was compacted | A compaction item was returned. Ask another question to test using it. |
| Compaction was used | A successful answer used previously compacted context. Measured differences are shown if both answers are complete. |
| Compaction was not applied | OCI rejected compaction, or it was paused. Full history was used; no compaction benefit is claimed. |
| Failed or incomplete answer | There is no complete comparison for that question. |

Input tokens are OCI-reported request tokens. Total tokens include input and output;
output can include reasoning tokens. Counts cover **successful responses only**:
usage consumed by failed attempts is unknown. The app does not calculate cost.

Answer time measures the complete request, including recovery, **not time to first
token**. The two chats run sequentially and alternate which goes first. Time waiting
for the other chat is excluded from each side's measurement. Differences are observed
results, not proof that compaction caused a change.

## Known OCI compatibility limitation

In local checks with `openai.gpt-oss-120b` in `us-chicago-1`, ordinary chat requests
worked after adapting replayed assistant text. Compaction-related requests also
returned HTTP 400 text-validation errors. Explicit compaction could return an item,
but continuing with that item failed validation in the observed deployment.
These observations do not establish behavior for every model, region, or deployment.

The app recognizes these specific format errors, retries once using full history
with compaction OFF, and pauses compaction on that side. **Retry compaction next
turn** allows another attempt. Authentication, quota, and unrelated errors do not
trigger this fallback. There is no automatic backoff retry loop.

See [troubleshooting](docs/troubleshooting.md) for symptoms and recovery, and
[architecture](docs/architecture.md) for history handling and comparison rules.

## Command-line examples

After installing dependencies and configuring `.env`:

```bash
.venv/bin/python compaction_demo.py explicit
.venv/bin/python compaction_demo.py automatic
```

Explicit mode normally makes three calls; automatic mode normally makes two and
builds synthetic history locally. The CLI prompts privately for a missing API key.
Unlike the chatbot, these examples surface provider failures without the chatbot's
full-history fallback. Preserve the complete returned compaction output and check
recall; a returned compaction item alone does not prove a successful continuation.

## Development and checks

```bash
.venv/bin/python -m unittest discover -v
bash -n start.sh
```

The unit tests are offline and require no OCI credentials. GitHub Actions installs
dependencies, runs them, and smoke-tests the initial UI on Python 3.11 and 3.13.
CI makes no OCI calls and does not validate live compaction or performance.
See [CONTRIBUTING.md](CONTRIBUTING.md) for local UI checks and change guidelines.

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit interface and paired chat sessions. |
| `chat_flow.py` | Independent histories, live requests, timing, and compatibility recovery. |
| `comparison.py` | Eligibility checks and plain-language measured differences. |
| `compaction_demo.py` | CLI examples and shared context serialization/adaptation. |
| `ui_demo.py` | Synthetic history and shared format-error detection; standalone two-request demo helper. |
| `test_*.py` | Offline history, recovery, measurement, and comparison checks. |

## Oracle references

- [Responses API](https://docs.oracle.com/en-us/iaas/Content/generative-ai/responses-api.htm)
- [Compaction tutorial](https://docs.oracle.com/en-us/iaas/Content/generative-ai/responses-api-compaction-tutorial.htm)
- [Compaction release note](https://docs.oracle.com/en-us/iaas/releasenotes/generative-ai/responses-api-compaction.htm)
- [OCI API errors and retry guidance](https://docs.oracle.com/en-us/iaas/Content/API/References/apierrors.htm)
