"""Serializable domain models used by audits, reports, and comparisons."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Any


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


SEVERITY_RANK: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


@dataclass(frozen=True)
class Finding:
    code: str
    title: str
    severity: Severity
    summary: str
    path: str = ""
    target: str = ""
    repair: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            {
                "code": self.code,
                "path": self.path,
                "target": self.target,
                "metadata": self.metadata,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(payload.encode("utf-8")).hexdigest()[:20]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "code": self.code,
            "title": self.title,
            "severity": self.severity.value,
            "summary": self.summary,
            "path": self.path,
            "target": self.target,
            "repair": self.repair,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Finding:
        return cls(
            code=str(value["code"]),
            title=str(value["title"]),
            severity=Severity(str(value["severity"])),
            summary=str(value["summary"]),
            path=str(value.get("path", "")),
            target=str(value.get("target", "")),
            repair=str(value.get("repair", "")),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "size": self.size, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> FileRecord:
        return cls(
            path=str(value["path"]),
            size=int(value["size"]),
            sha256=str(value["sha256"]),
        )


@dataclass
class AuditReport:
    schema_version: str
    tool_version: str
    generated_at: str
    input_kind: str
    input_label: str
    adapters: list[str]
    status: str
    readiness_score: int
    metrics: dict[str, int]
    severity_counts: dict[str, int]
    findings: list[Finding]
    files: list[FileRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tool": {"name": "exitpreflight", "version": self.tool_version},
            "generated_at": self.generated_at,
            "input": {"kind": self.input_kind, "label": self.input_label},
            "adapters": self.adapters,
            "summary": {
                "status": self.status,
                "readiness_score": self.readiness_score,
                "severity_counts": self.severity_counts,
            },
            "metrics": self.metrics,
            "findings": [finding.to_dict() for finding in self.findings],
            "files": [record.to_dict() for record in self.files],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AuditReport:
        tool = dict(value.get("tool", {}))
        input_value = dict(value.get("input", {}))
        summary = dict(value.get("summary", {}))
        return cls(
            schema_version=str(value["schema_version"]),
            tool_version=str(tool.get("version", "unknown")),
            generated_at=str(value.get("generated_at", "")),
            input_kind=str(input_value.get("kind", "unknown")),
            input_label=str(input_value.get("label", "")),
            adapters=[str(item) for item in value.get("adapters", [])],
            status=str(summary.get("status", "unknown")),
            readiness_score=int(summary.get("readiness_score", 0)),
            metrics={str(key): int(item) for key, item in dict(value.get("metrics", {})).items()},
            severity_counts={
                str(key): int(item)
                for key, item in dict(summary.get("severity_counts", {})).items()
            },
            findings=[Finding.from_dict(item) for item in value.get("findings", [])],
            files=[FileRecord.from_dict(item) for item in value.get("files", [])],
        )


def meets_threshold(severity: Severity, threshold: Severity) -> bool:
    return SEVERITY_RANK[severity] >= SEVERITY_RANK[threshold]
