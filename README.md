# ExitPreflight

**Audit a SaaS export before you delete, downgrade, or migrate the account.**

[![CI](https://github.com/KanadeK/exitpreflight/actions/workflows/ci.yml/badge.svg)](https://github.com/KanadeK/exitpreflight/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/KanadeK/exitpreflight)](https://github.com/KanadeK/exitpreflight/releases)
[![Python](https://img.shields.io/badge/python-3.11%2B-244b71)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-006b52)](LICENSE)

Downloading a ZIP proves that a download finished. It does **not** prove that the export is
self-contained, complete enough to recover, or safe to extract. ExitPreflight reads the export
locally, inventories and hashes every file, parses service-specific records, and produces an
evidence bundle before the source account disappears.

```text
$ exitpreflight audit takeout.zip -o preflight --strict
ExitPreflight: needs-attention | score 31/100 | 7 findings | 1,248 files
Reports: .../preflight
  - exitpreflight-report.json
  - exitpreflight-report.md
  - exitpreflight-report.html
  - manifest.sha256
  - rescue-plan.csv
```

No account, API key, database, browser extension, or upload is required. Runtime dependencies:
**zero**.

## What it actually checks

| Input | Real checks in v0.1.0 |
| --- | --- |
| Any directory, ZIP, TAR, TAR.GZ, TGZ | CRC, unsafe paths, link entries, case/normalized collisions, zero-byte files, SHA-256 manifest, broken local references, cloud-only and signed URLs |
| Slack JSON export | Channel/user/message counts, missing channel folders, unknown users, malformed JSON, attachment links that are not exported files |
| Google Takeout / Gmail MBOX | Streaming message count, labels, attachment count, malformed/oversized messages, cloud-only references, missing `archive_browser.html` in Takeout-like layouts |
| Notion Markdown/HTML/CSV | Page/database counts, broken attachments and local links, surviving Notion web dependencies, duplicate human titles after IDs are removed |
| Two audit reports | Missing/added/changed files and negative service-count deltas between exports |

ExitPreflight does not guess that an HTTP 200 response means a backup exists. It stays offline and
asks a narrower question: **is the referenced content present in this export?**

## Quick start

### From the repository

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .

exitpreflight demo -o exitpreflight-demo
exitpreflight audit examples/portable-export -o portable-report --strict
exitpreflight audit examples/risky-export -o risky-report --strict
```

The portable example exits `0`. The risky example writes all reports and exits `1`, because it
contains a missing Notion attachment, a Notion cloud dependency, a Slack file link without the
file, and a Drive-only Gmail reference.

### Standalone release artifact

Download `exitpreflight-0.1.0.pyz` and `SHA256SUMS` from the GitHub Release, verify its hash, then:

```bash
python exitpreflight-0.1.0.pyz audit /path/to/export.zip -o preflight --strict
```

## Commands and exit codes

```bash
# Build the five-file evidence bundle
exitpreflight audit EXPORT -o REPORT_DIR

# Make paths and external targets safe to share in an issue
exitpreflight audit EXPORT -o SHARE_DIR --share-safe

# Fail CI or a deletion checklist on high/critical findings
exitpreflight audit EXPORT -o REPORT_DIR --strict

# Detect silent losses between two exports
exitpreflight compare old/exitpreflight-report.json new/exitpreflight-report.json \
  -o comparison --strict

# Prove an audited export has not changed
exitpreflight verify EXPORT --manifest REPORT_DIR/manifest.sha256 --strict-extra
```

| Exit | Meaning |
| ---: | --- |
| `0` | Command completed; the configured finding threshold was not crossed |
| `1` | Audit/compare/verify completed, but findings or mismatches crossed the requested gate |
| `2` | Input, manifest, archive, JSON report, or filesystem operation was invalid |

`audit` writes the report before returning `1`. A failing gate never hides the evidence needed to
repair it.

## Evidence bundle

- `exitpreflight-report.html` — offline, responsive human review; all untrusted text is escaped.
- `exitpreflight-report.json` — versioned schema for automation and baseline comparison.
- `exitpreflight-report.md` — issue/checklist-ready summary.
- `manifest.sha256` — every exported file, sorted by portable path.
- `rescue-plan.csv` — cloud links, signed URLs, missing targets, and the concrete recovery action.

Reports contain local filenames and URLs by default because those are needed for recovery. Use
`--share-safe` before posting a report publicly; it replaces paths and targets with stable hashes.

## Trust boundary

ExitPreflight is deliberately read-only toward the source export:

- archives are inspected without extracting them;
- directory symlinks and TAR links are not followed;
- absolute and parent-traversal archive paths are blocked and reported;
- individual text/message parsing has safety limits;
- no network calls, telemetry, analytics, or automatic downloads occur;
- report writes are atomic and go only to the output directory you choose.

Read the full [threat model](docs/THREAT_MODEL.md) before auditing hostile archives.

## Verification and repair

The complete local gate is one command:

```bash
python -m pip install -e ".[dev]"
python scripts/verify.py
```

For exact acceptance steps, expected exit codes, package inspection, and clean-environment checks,
see [Acceptance](docs/ACCEPTANCE.md). If anything fails, follow the symptom-to-fix flow in
[Repair playbook](docs/REPAIR.md). Architecture and extension seams are documented in
[Architecture](docs/ARCHITECTURE.md).

## Scope and novelty

ExitPreflight is not a sync client, importer, backup daemon, migration service, mailbox search UI,
generic antivirus, or Notion-only link fixer. It is a local, cross-service **pre-deletion
recoverability gate** with comparable metrics and cryptographic receipts.

The bounded research and overlap audit behind that scope—including nearby projects that were
rejected—is public in [Research and selection](docs/RESEARCH.md). Star counts are never
guaranteed; the project is designed for a concrete, current pain point, a one-command demo, a
privacy-respecting default, and outputs people can verify.

## Contributing

New adapters should add detection signals, service metrics, deterministic findings, synthetic
fixtures, and failure-path tests without adding network access to the default audit. Start with
[CONTRIBUTING.md](CONTRIBUTING.md).

MIT © KanadeK. Synthetic fixtures contain no real account data.
