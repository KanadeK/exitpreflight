"""Audit orchestration and deterministic readiness scoring."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .adapters import AuditAccumulator, detect_adapters, run_adapters
from .models import SEVERITY_RANK, AuditReport, FileRecord, Finding, Severity
from .source import ExportSource

WEIGHTS: dict[Severity, int] = {
    Severity.CRITICAL: 30,
    Severity.HIGH: 12,
    Severity.MEDIUM: 5,
    Severity.LOW: 1,
    Severity.INFO: 0,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _deduplicate(findings: list[Finding]) -> list[Finding]:
    by_fingerprint: dict[str, Finding] = {}
    for finding in findings:
        by_fingerprint.setdefault(finding.fingerprint, finding)
    return sorted(
        by_fingerprint.values(),
        key=lambda item: (
            -SEVERITY_RANK[item.severity],
            item.code,
            item.path.casefold(),
            item.target.casefold(),
        ),
    )


def _readiness_score(findings: list[Finding]) -> int:
    deductions = sum(WEIGHTS[finding.severity] for finding in findings)
    return max(0, 100 - deductions)


def audit_export(
    input_path: str | Path,
    *,
    clock: Callable[[], datetime] = _now,
    max_findings_per_code: int = 60,
) -> AuditReport:
    with ExportSource(input_path) as source:
        adapters = detect_adapters(source)
        acc = AuditAccumulator(max_findings_per_code=max_findings_per_code)
        for finding in source.structural_findings:
            acc.add(finding)
        for finding in source.test_integrity():
            acc.add(finding)
        run_adapters(source, adapters, acc)
        files = [
            FileRecord(path=name, size=source.entries[name].size, sha256=source.hash(name))
            for name in source.names()
        ]
        findings = _deduplicate(acc.findings)
        counts = Counter(finding.severity.value for finding in findings)
        severity_counts = {severity.value: counts[severity.value] for severity in Severity}
        score = _readiness_score(findings)
        status = (
            "blocked"
            if severity_counts[Severity.CRITICAL.value]
            else "needs-attention"
            if severity_counts[Severity.HIGH.value]
            else "review"
            if severity_counts[Severity.MEDIUM.value]
            else "ready"
        )
        return AuditReport(
            schema_version="1.0",
            tool_version=__version__,
            generated_at=clock().astimezone(UTC).isoformat().replace("+00:00", "Z"),
            input_kind=source.kind,
            input_label=str(source.path),
            adapters=adapters,
            status=status,
            readiness_score=score,
            metrics=dict(sorted(acc.metrics.items())),
            severity_counts=severity_counts,
            findings=findings,
            files=files,
        )
