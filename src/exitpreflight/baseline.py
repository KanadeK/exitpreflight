"""Compare two audit reports and surface silent export regressions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import AuditReport

COUNT_METRIC_PREFIXES = ("files.", "slack.", "gmail.", "notion.")


def load_report(path: str | Path) -> AuditReport:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Audit report must be a JSON object.")
    return AuditReport.from_dict(value)


def compare_reports(before: AuditReport, after: AuditReport) -> dict[str, Any]:
    before_files = {record.path: record for record in before.files}
    after_files = {record.path: record for record in after.files}
    missing = sorted(set(before_files) - set(after_files), key=str.casefold)
    added = sorted(set(after_files) - set(before_files), key=str.casefold)
    changed = sorted(
        (
            path
            for path in set(before_files) & set(after_files)
            if before_files[path].sha256 != after_files[path].sha256
        ),
        key=str.casefold,
    )
    metric_keys = sorted(set(before.metrics) | set(after.metrics))
    metric_deltas = {
        key: {
            "before": before.metrics.get(key, 0),
            "after": after.metrics.get(key, 0),
            "delta": after.metrics.get(key, 0) - before.metrics.get(key, 0),
        }
        for key in metric_keys
    }
    regressions = [
        {"metric": key, **value}
        for key, value in metric_deltas.items()
        if value["delta"] < 0 and key.startswith(COUNT_METRIC_PREFIXES)
    ]
    status = "regressed" if missing or regressions else "changed" if added or changed else "stable"
    return {
        "schema_version": "1.0",
        "tool": {"name": "exitpreflight", "mode": "compare"},
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "summary": {
            "status": status,
            "missing_files": len(missing),
            "added_files": len(added),
            "changed_files": len(changed),
            "metric_regressions": len(regressions),
        },
        "before": {"generated_at": before.generated_at, "input": before.input_label},
        "after": {"generated_at": after.generated_at, "input": after.input_label},
        "metric_deltas": metric_deltas,
        "regressions": regressions,
        "files": {"missing": missing, "added": added, "changed": changed},
    }
