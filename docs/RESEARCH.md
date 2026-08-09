# Research and selection

Research date: 2026-08-08. This is a bounded market and overlap audit, not a claim that every public
or private repository on Earth was inspected.

## Portfolio boundary

The local portfolio was inventoried before selection. It already contained developer/repository
analysis, data privacy, archive safety, email rule replay, support-mail triage, Notion-adjacent
workflows, file delivery receipts, release tooling, document preflight, and local-first utilities.
Rejected concepts included another docs-drift checker, coding-agent handoff tool, mailbox search UI,
Notion-only fixer, generic ZIP scanner, and file inbox organizer. ExitPreflight's retained boundary is
cross-service export **recoverability before destructive account change**.

## Demand evidence

- Slack's official export guide states that normal JSON exports contain links to files rather than
  the files themselves; plan/scope and retention also change what is included:
  <https://slack.com/help/articles/204897248-Guide-to-Slack-import-and-export-tools-Guide-to-Slack-import-and-export-tools>.
- Slack's reading guide repeats that JSON export ZIPs contain file links and no workspace files:
  <https://slack.com/help/articles/220556107-How-to-read-Slack-data-exports>.
- Google says Takeout may omit recent changes made between request and archive creation, and advises
  regenerating or splitting an archive when it fails:
  <https://support.google.com/accounts/answer/3024190>.
- Recent Notion users still report missing images, broken database relations, and mistrust of native
  exports: <https://www.reddit.com/r/Notion/comments/1s737lv/does_anyone_actually_trust_notions_native_export/>.
- A recent Google Takeout discussion describes cloud links that were not included and accidental
  loss during manual cleanup:
  <https://www.reddit.com/r/degoogle/comments/1uv2v09/google_takeout_shows_why_you_should_own_your_own/>.

These are concrete failure modes with a time boundary: once access or retention ends, repair can be
impossible.

## Nearby projects inspected

| Project/category | What it does | Why it is not this project |
| --- | --- | --- |
| Offpedia Notion Export Auditor | Audits Notion-to-Obsidian cleanup risks | Notion-specific and tied to a larger site workflow; no cross-service baseline/manifest contract |
| Vault Inspector | Finds broken links, orphan attachments, and metadata issues in Obsidian | Audits an active Obsidian vault, not source SaaS exports before account deletion |
| OpenArchiver / msgvault | Ingest, index, search, and retain email/chat | Archive/search platforms; not a zero-dependency export preflight and cross-format receipt |
| ArchiveBox | Captures web pages behind links | Networked web archiving; does not establish whether a SaaS export is already self-contained |
| notion-exporter family | Produces or converts Notion exports | Export/migration generation rather than independent post-export verification |
| docs-drift tools (Drift, DocDecay, hosted bots) | Detect stale docs as code changes | Crowded developer-doc problem, unrelated to personal/business data portability |
| agent handoff tools (Entire skills, `continues`) | Transfer coding-session context | Fast-growing but already implemented by multiple current projects |

Searches used GitHub CLI where available, GitHub/web search, official vendor documentation, and
current community discussions. GitHub repository search hit its authenticated search-rate limit
during the broader pass; ordinary web/GitHub result pages were used as the fallback. No sampled
project combined all of these properties: local/offline, directory and archive inputs, Slack +
Gmail/Takeout + Notion structural parsing, cloud-only dependency detection, cross-export regression,
and cryptographic manifest verification.

## Selection matrix

Scores are 1 (weak) to 5 (strong).

| Candidate | Concrete pain | Low direct competition | Demo in one command | Distinct from local portfolio | Release-sized core | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Documentation drift detector | 5 | 1 | 4 | 2 | 3 | 15 |
| Cross-agent session handoff | 5 | 1 | 4 | 1 | 3 | 14 |
| Local mailbox search/context graph | 4 | 1 | 3 | 2 | 2 | 12 |
| Notion export fixer | 4 | 2 | 4 | 2 | 4 | 16 |
| **Cross-SaaS export preflight** | **5** | **4** | **5** | **5** | **4** | **23** |

## Visibility hypothesis

High stars cannot be promised. The selected scope has stronger discoverability ingredients than a
generic productivity shell:

- a seven-word problem statement tied to an irreversible moment;
- recent official and community evidence;
- local-first/no-account privacy boundary;
- useful output on the first command with synthetic data;
- service keywords people already search (`Google Takeout`, `Slack export`, `Notion export`);
- machine-readable evidence for maintainers and an offline report for non-developers;
- adapters that allow community contributions without rewriting the engine.

Promotion or manufactured stars are out of scope. Adoption must come from a real workflow and
verifiable behavior.
