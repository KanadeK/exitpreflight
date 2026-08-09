# Repository instructions

- Keep the runtime dependency-free on Python 3.11+.
- Default audit paths must remain offline and read-only toward the input export.
- Never commit real exports, mailbox data, signed URLs, tokens, or unredacted reports.
- Every new finding needs a stable code, severity, evidence location, repair text, and test.
- Every new service metric needs a comparison regression test.
- Run `python scripts/verify.py` before committing and `python scripts/release_check.py --require-clean` before tagging.
- Do not lower coverage, lint, typing, deterministic-package, author, or checksum gates to make a change pass.
