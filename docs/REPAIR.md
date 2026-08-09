# Repair playbook

Start with the command's exit code, then the finding code in JSON/HTML. Do not delete the source
account while a critical/high finding is unexplained.

| Symptom or code | Likely cause | Repair | Re-run |
| --- | --- | --- | --- |
| Exit `2`, unsupported input | A PDF/JSON file was passed directly, or the archive format is unsupported | Export/unpack into a directory, ZIP, TAR, TAR.GZ, or TGZ without modifying source records | Original command |
| `archive-crc-failure` | Interrupted/corrupt ZIP download | Download all parts again; compare vendor size/checksum if available | `audit ... --strict` |
| `archive-unsafe-path` / `archive-link-entry` | Export or repacker created traversal/link members | Do not extract normally; request a clean export or rebuild in isolation with regular relative files | Audit the replacement |
| `archive-case-collision` | Two source names differ only by case | Rename one source item before export; preserve both originals until verified | Audit on Windows and a case-sensitive CI runner |
| `missing-local-target` | Attachment/page was omitted or renamed | Recover it from the source service, store it in the export tree, update the link, and create a new manifest | `audit`, then `verify` |
| `cloud-link-dependency` / `signed-url-dependency` | Export kept a web pointer instead of content | Download while authenticated, record source path/message, replace with a local reference | Audit the rescued copy |
| `slack-file-link-only` | Slack JSON exports file links rather than bytes | Download attachments before workspace access/retention expires; keep link-to-file mapping | Audit the combined folder |
| `slack-user-reference-missing` | Export scope or member directory is incomplete | Export/preserve `users.json`, confirm plan/date scope, or document the irrecoverable identity | Compare a fresh report |
| `mbox-no-messages` / `mbox-message-unreadable` | Incomplete split download or malformed MBOX | Re-export Gmail alone in smaller parts; open with a trusted mail client; retain both copies | Audit and compare counts |
| `gmail-labels-missing` | Non-Takeout MBOX or stripped headers | Confirm `X-Gmail-Labels` exists in raw messages; regenerate from Takeout if organization matters | Audit replacement |
| `takeout-browser-missing` | Split archive parts were not combined | Download every part and place/extract them under one common root | Audit common root |
| Compare status `regressed` | New export lost files or service counts | Check scope/date/retention, preserve the older export, regenerate, and explain intentional deletions | Compare again |
| Manifest mismatch | File changed after audit | Restore from immutable copy or intentionally re-audit and issue a new manifest | `verify --strict-extra` |
| Coverage/lint/type gate fails | Code path or contract changed without equivalent tests/types | Fix the first reported file; avoid lowering thresholds to hide the failure | `python scripts/verify.py` |
| Clean-environment install fails | Wheel/package data or entry point is incomplete | Inspect wheel contents, fix `pyproject.toml`, rebuild, then rerun release preflight | `python scripts/release_check.py` |

## Privacy incident during reporting

If a public issue received an unredacted report, remove the attachment/comment where the platform
allows, rotate any signed URL or token that appeared, revoke public shares, and repost only a
`--share-safe` report plus synthetic fixture. Hash aliases protect names, not facts in free-text
summaries you manually add.
