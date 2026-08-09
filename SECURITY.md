# Security policy

## Supported versions

Security fixes are provided for the latest released minor version.

## Report privately

Use GitHub's **Security → Report a vulnerability** flow for archive traversal, report injection,
resource-exhaustion, privacy leakage, or release-integrity issues. Do not attach a real export,
mailbox, Slack workspace, signed URL, access token, or unredacted report.

Include a minimal synthetic archive, the ExitPreflight version, operating system, command, expected
behavior, and observed behavior. If the issue itself is the redaction layer, use invented paths and
URLs that demonstrate the same parsing structure.

## Security posture

ExitPreflight performs no network requests and does not extract archives. It still parses untrusted
bytes. Run hostile files in an isolated account or virtual machine and review
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).
