# Contributing

Use Python 3.11+ and install `requirements.txt` in a virtual environment.
Start with the [README](README.md), [architecture](docs/architecture.md), and
[troubleshooting guide](docs/troubleshooting.md).

## Local checks

```bash
.venv/bin/python -m unittest discover -v
bash -n start.sh
```

Run an initial UI smoke check without making OCI calls:

```bash
.venv/bin/python -c 'from streamlit.testing.v1 import AppTest; app = AppTest.from_file("app.py").run(timeout=20); assert not app.exception; assert len(app.chat_input) == 1'
```

The unit tests and initial UI check require no credentials. Live checks use real OCI
quota and should be run explicitly from a configured local environment.
GitHub Actions performs offline checks on Python 3.11 and 3.13.

## Changes to history or comparison behavior

Preserve encrypted context and tool items. Keep the full-history recovery copy
independent of the compacted branch. Cover behavior changes with tests that verify
history retention, error boundaries, measurement accuracy, or benefit eligibility.
Never label fallback or a merely returned compaction item as proven savings.

Before opening a pull request, describe the resulting behavior, verification, and
any remaining provider limitation. Keep credentials, private prompts, local `.env`
files, and exported measurements out of commits and issue reports.
