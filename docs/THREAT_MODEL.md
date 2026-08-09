# Threat model

## Protected assets

- private filenames, page titles, people, message metadata, and URLs;
- integrity and availability of the user's export and filesystem;
- confidence that a report corresponds to the bytes that were audited;
- predictable CPU, memory, and disk use when opening large or hostile archives.

## Adversaries and failures

- a corrupt or malicious archive with traversal, duplicate, link, collision, CRC, or compression
  hazards;
- exported HTML/Markdown/JSON containing script-like strings intended to break the report;
- huge text records or email messages intended to exhaust memory;
- signed links and cloud permissions that expire after the source account is deleted;
- accidental publication of paths, message context, or access-bearing URLs;
- silent changes between an initial export and a later export.

## Controls in v0.1.0

- no archive extraction, network request, browser execution, telemetry, or credential handling;
- normalized relative paths and explicit traversal/absolute-path rejection;
- directory symlinks and TAR links are reported and never followed;
- ZIP CRC testing, entry/expanded-size limits, compression-ratio findings, and streaming hashes;
- 8 MiB generic text and 64 MiB per-message inspection limits;
- capped repeated findings with aggregate suppression metrics;
- HTML escaping and atomic output replacement;
- optional stable-hash redaction for paths and targets;
- SHA-256 manifest and cross-export count comparison.

## Residual risk

- standard-library parsers can still contain vulnerabilities; audit hostile archives in isolation;
- hashing a very large export is intentionally I/O intensive;
- the tool cannot detect source data omitted without any trace or know the vendor's true total;
- known cloud-host classification is finite and requires maintenance;
- `--share-safe` does not sanitize arbitrary prose a user adds after generation;
- a clean structural report is not legal/compliance advice and not proof of successful re-import.

## Non-goals

ExitPreflight does not log into services, bypass access controls, download private targets, decrypt
archives, execute exported scripts, render remote content, repair bytes automatically, or delete
accounts.
