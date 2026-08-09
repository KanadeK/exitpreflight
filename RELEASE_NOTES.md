# ExitPreflight v0.1.0

The first public release turns SaaS export review into a repeatable, offline gate.

## Highlights

- Audit directories and ZIP/TAR exports without extraction or network access.
- Parse Slack JSON, Gmail MBOX, Google Takeout layouts, and Notion exports.
- Find cloud-only attachments, signed/expiring URLs, broken local references, malformed records,
  archive path hazards, and count regressions.
- Produce an offline HTML report, JSON/Markdown evidence, a rescue CSV, and `manifest.sha256`.
- Compare two exports and verify that an audited copy has not changed.
- Run from an installed package or the standalone `exitpreflight-0.1.0.pyz` release asset.

## Verify downloads

Download `SHA256SUMS` with the release assets, then use your platform's SHA-256 tool. For example:

```bash
sha256sum -c SHA256SUMS
python exitpreflight-0.1.0.pyz --version
```

Windows PowerShell users can compare `Get-FileHash -Algorithm SHA256 <asset>` with the matching
line in `SHA256SUMS`.

## Known boundaries

- ExitPreflight reports cloud dependencies but never downloads them automatically.
- A clean result proves the configured structural and referential checks passed; it cannot prove
  that a source service exported data it never disclosed.
- Service export formats can change. Unknown fields are preserved in the source and ignored unless
  a validator explicitly consumes them.
