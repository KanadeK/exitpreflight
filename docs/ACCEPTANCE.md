# Acceptance

These commands prove the repository contains working behavior, not a UI shell.

## 1. Clean setup

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## 2. Full local gate

```bash
python scripts/verify.py
```

Expected: formatting, lint, type checks, branch coverage, compilation, CLI smoke tests, healthy and
risky fixture gates, package build, secret scan, and release-asset construction all pass.

## 3. Prove both exit paths

```bash
exitpreflight audit examples/portable-export -o .accept/portable --strict
# expected exit: 0

exitpreflight audit examples/risky-export -o .accept/risky --strict
# expected exit: 1; five report artifacts still exist
```

PowerShell can display the most recent exit code with `$LASTEXITCODE`; POSIX shells use `echo $?`.

## 4. Verify tamper evidence

```bash
exitpreflight verify examples/portable-export \
  --manifest .accept/portable/manifest.sha256 --strict-extra
# expected exit: 0
```

Copy the sample, modify `assets/receipt.txt`, and run verification against the original manifest.
Expected exit: `1` with `mismatched: assets/receipt.txt`.

## 5. Compare exports

Audit an older and newer export, then:

```bash
exitpreflight compare old/exitpreflight-report.json new/exitpreflight-report.json \
  -o .accept/comparison --strict
```

Missing files or lower Slack/Gmail/Notion counts must return `1` and be listed in both comparison
artifacts.

## 6. Release preflight

After committing the intended source:

```bash
python scripts/release_check.py --require-clean
```

Expected checks include:

- version and required-file consistency;
- full verification gate;
- two deliberately separate package builds with byte-identical artifacts;
- import and CLI audit in a clean virtual environment;
- author/committer allowlist and absence of `Co-authored-by` trailers;
- release asset checksums and ZIP member inspection.

The GitHub repository, Actions run, tag, Release, downloaded asset hashes, and contributor list are
separate online gates. A green local preflight alone is not a public release.
