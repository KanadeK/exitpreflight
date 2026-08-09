# Contributing

Thanks for helping people leave cloud services with fewer surprises.

## Setup

```bash
python -m venv .venv
# Activate the environment for your shell.
python -m pip install -e ".[dev]"
python scripts/verify.py
```

## Adapter contract

Every service adapter must include:

1. two or more stable detection signals so unrelated folders are not mislabeled;
2. count metrics that can expose losses between exports;
3. findings with severity, evidence path, reason, and a concrete repair action;
4. synthetic fixtures containing no personal or vendor-secret data;
5. success, malformed-input, and failure-path tests;
6. no network request in the default audit path.

Do not submit real Takeout, workspace, mailbox, employee, or customer exports. Reduce a report to a
synthetic fixture and use `--share-safe` for diagnostics.

## Pull request gate

```bash
python scripts/verify.py
python scripts/release_check.py
```

Describe the export format version or official documentation used, what count can regress, and how
a user repairs each new high/critical finding.
