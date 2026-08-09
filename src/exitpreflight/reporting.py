"""Privacy-aware JSON, Markdown, HTML, CSV, and manifest report writers."""

from __future__ import annotations

import csv
import html
import io
import json
import os
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from .manifest import render_manifest
from .models import AuditReport

REPORT_JSON = "exitpreflight-report.json"
REPORT_HTML = "exitpreflight-report.html"
REPORT_MARKDOWN = "exitpreflight-report.md"
MANIFEST = "manifest.sha256"
RESCUE_PLAN = "rescue-plan.csv"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        Path(temporary).replace(path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _alias(value: str, prefix: str) -> str:
    if not value:
        return ""
    return f"{prefix}-{sha256(value.encode('utf-8')).hexdigest()[:12]}"


def _share_safe(value: dict[str, Any]) -> dict[str, Any]:
    cleaned = cast(dict[str, Any], json.loads(json.dumps(value, ensure_ascii=False)))
    cleaned["input"]["label"] = _alias(str(cleaned["input"].get("label", "")), "input")
    for file_value in cleaned.get("files", []):
        file_value["path"] = _alias(str(file_value.get("path", "")), "file")
    for finding in cleaned.get("findings", []):
        finding["path"] = _alias(str(finding.get("path", "")), "file")
        finding["target"] = _alias(str(finding.get("target", "")), "target")
        metadata = finding.get("metadata")
        if isinstance(metadata, dict) and "resolved_path" in metadata:
            metadata["resolved_path"] = _alias(str(metadata["resolved_path"]), "file")
    return cleaned


def report_dict(report: AuditReport, *, share_safe: bool = False) -> dict[str, Any]:
    value = report.to_dict()
    return _share_safe(value) if share_safe else value


def render_markdown(value: dict[str, Any]) -> str:
    summary = value["summary"]
    lines = [
        "# ExitPreflight report",
        "",
        f"- Status: **{summary['status']}**",
        f"- Readiness score: **{summary['readiness_score']}/100**",
        f"- Adapters: {', '.join(value['adapters'])}",
        f"- Files: {len(value.get('files', []))}",
        "",
        "## Findings",
        "",
    ]
    findings = value.get("findings", [])
    if not findings:
        lines.append("No findings.")
    for finding in findings:
        location = f" — `{finding['path']}`" if finding.get("path") else ""
        lines.extend(
            [
                f"### [{finding['severity'].upper()}] {finding['title']}{location}",
                "",
                finding["summary"],
                "",
                f"Repair: {finding['repair'] or 'Review the source export.'}",
                "",
            ]
        )
    lines.extend(["## Metrics", "", "| Metric | Value |", "| --- | ---: |"])
    for key, item in sorted(value.get("metrics", {}).items()):
        lines.append(f"| `{key}` | {item} |")
    return "\n".join(lines) + "\n"


def render_html(value: dict[str, Any]) -> str:
    summary = value["summary"]
    rows = []
    for finding in value.get("findings", []):
        rows.append(
            "<tr>"
            f"<td><span class='pill {html.escape(finding['severity'])}'>{html.escape(finding['severity'])}</span></td>"
            f"<td><strong>{html.escape(finding['title'])}</strong><br><code>{html.escape(finding.get('code', ''))}</code></td>"
            f"<td>{html.escape(finding.get('path', ''))}</td>"
            f"<td>{html.escape(finding['summary'])}<br><small>{html.escape(finding.get('repair', ''))}</small></td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='4'>No findings.</td></tr>")
    metrics = "".join(
        f"<tr><td><code>{html.escape(key)}</code></td><td>{item}</td></tr>"
        for key, item in sorted(value.get("metrics", {}).items())
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ExitPreflight report</title>
<style>
:root{{--bg:#f5f3ee;--ink:#19211d;--muted:#66716a;--panel:#fffdf8;--line:#d8ddd7;--accent:#006b52}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif}}
main{{max-width:1120px;margin:auto;padding:48px 24px}} h1{{font-size:clamp(2rem,5vw,4rem);letter-spacing:-.05em;margin:.1em 0}}
.eyebrow{{color:var(--accent);font-weight:800;text-transform:uppercase;letter-spacing:.12em}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:24px 0}}
.card,section{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}} .big{{font-size:2rem;font-weight:800}} .muted,small{{color:var(--muted)}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}} code{{overflow-wrap:anywhere}}
.pill{{display:inline-block;border-radius:999px;padding:3px 9px;font-weight:800;background:#e8ece9}} .critical{{background:#ffd5d1}} .high{{background:#ffe0b5}} .medium{{background:#fff2b8}} .low{{background:#dcecff}}
@media(max-width:700px){{th:nth-child(3),td:nth-child(3){{display:none}} main{{padding:24px 12px}}}}
</style></head><body><main>
<div class="eyebrow">Local export recoverability</div><h1>ExitPreflight</h1>
<p class="muted">Generated {html.escape(value.get("generated_at", ""))}. No data was uploaded by this report.</p>
<div class="grid"><div class="card"><div class="muted">Status</div><div class="big">{html.escape(summary["status"])}</div></div>
<div class="card"><div class="muted">Readiness</div><div class="big">{summary["readiness_score"]}/100</div></div>
<div class="card"><div class="muted">Files</div><div class="big">{len(value.get("files", []))}</div></div>
<div class="card"><div class="muted">Adapters</div><div class="big">{len(value.get("adapters", []))}</div><small>{html.escape(", ".join(value.get("adapters", [])))}</small></div></div>
<section><h2>Findings</h2><div style="overflow:auto"><table><thead><tr><th>Severity</th><th>Finding</th><th>Path</th><th>Why it matters / repair</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>
<section style="margin-top:16px"><h2>Metrics</h2><table><tbody>{metrics}</tbody></table></section>
</main></body></html>"""


def render_rescue_csv(value: dict[str, Any]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["severity", "code", "source", "target", "repair"])
    for finding in value.get("findings", []):
        if finding.get("target") and finding.get("code") in {
            "cloud-link-dependency",
            "signed-url-dependency",
            "slack-file-link-only",
            "gmail-cloud-only-reference",
            "missing-local-target",
        }:
            writer.writerow(
                [
                    finding.get("severity", ""),
                    finding.get("code", ""),
                    finding.get("path", ""),
                    finding.get("target", ""),
                    finding.get("repair", ""),
                ]
            )
    return stream.getvalue()


def write_report_bundle(
    report: AuditReport, output_dir: str | Path, *, share_safe: bool = False
) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    value = report_dict(report, share_safe=share_safe)
    artifacts = {
        REPORT_JSON: json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        REPORT_MARKDOWN: render_markdown(value),
        REPORT_HTML: render_html(value),
        MANIFEST: render_manifest(report.files),
        RESCUE_PLAN: render_rescue_csv(value),
    }
    paths: list[Path] = []
    for name, content in artifacts.items():
        path = destination / name
        _atomic_write(path, content)
        paths.append(path)
    return paths


def write_comparison(value: dict[str, Any], output_dir: str | Path) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "exitpreflight-compare.json"
    markdown_path = destination / "exitpreflight-compare.md"
    _atomic_write(json_path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    summary = value["summary"]
    lines = [
        "# ExitPreflight comparison",
        "",
        f"Status: **{summary['status']}**",
        "",
        f"- Missing files: {summary['missing_files']}",
        f"- Added files: {summary['added_files']}",
        f"- Changed files: {summary['changed_files']}",
        f"- Metric regressions: {summary['metric_regressions']}",
        "",
        "## Metric regressions",
        "",
    ]
    if not value["regressions"]:
        lines.append("No count regressions detected.")
    for regression in value["regressions"]:
        lines.append(
            f"- `{regression['metric']}`: {regression['before']} -> {regression['after']} ({regression['delta']})"
        )
    _atomic_write(markdown_path, "\n".join(lines) + "\n")
    return [json_path, markdown_path]
