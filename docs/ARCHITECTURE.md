# Architecture

ExitPreflight separates evidence collection from service interpretation so a new adapter cannot
silently weaken archive safety or reporting.

```text
directory / ZIP / TAR
        │
        ▼
 ExportSource ── path normalization, link refusal, CRC, streaming reads
        │
        ├── Generic audit ── file hashes, local refs, cloud/signed URLs
        ├── Slack adapter ── users/channels/messages/file links
        ├── Gmail adapter ── streaming MBOX/messages/labels/attachments
        └── Notion adapter ── pages/databases/title ambiguity
        │
        ▼
 AuditReport v1 ── deterministic findings, metrics, readiness score
        │
        ├── JSON / Markdown / HTML / rescue CSV / SHA-256 manifest
        ├── compare(old, new)
        └── verify(export, manifest)
```

## Boundaries

### `source.py`

Creates a portable POSIX-path view without extraction. Absolute paths, `..`, duplicate normalized
members, case collisions, TAR links, symlinks, CRC failures, entry counts, expanded size, and
extreme compression ratios are handled before service parsing. Archive streams remain open only for
the audit context.

### `links.py`

Extracts Markdown, HTML, and plain HTTP references. It distinguishes local, ordinary external,
known cloud-hosted, and signed/expiring URLs. Only local/cloud/signed references affect
recoverability; ordinary web citations are not treated as backup failures.

### `adapters.py`

Detection uses structural signals, never just a user-supplied label. Adapters add metrics and
findings through `AuditAccumulator`, which caps repeated findings by code and records suppression
counts. This prevents a million-message export from creating an unusable report while keeping the
aggregate evidence.

### `engine.py` and `models.py`

The engine hashes all files, deduplicates findings by stable fingerprint, calculates severity
counts, and creates `AuditReport` schema `1.0`. The score is an explanation aid, not a probability:
critical/high/medium/low findings deduct 30/12/5/1 points. Status is driven by the highest severity.

### `reporting.py`

All formats derive from the same report object. HTML escapes untrusted strings. Writes use a
same-directory temporary file plus atomic replacement. `--share-safe` hashes input labels, paths,
targets, and resolved paths while retaining stable correlation across report formats.

## Extension rule

An adapter may interpret source bytes and emit evidence. It may not mutate the export, extract an
archive, contact the source service, download a missing target, or silently downgrade a generic
finding. Network-assisted rescue belongs in an explicit future command with a separate consent and
credential boundary.
