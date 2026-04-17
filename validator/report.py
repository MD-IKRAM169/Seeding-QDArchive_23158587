from __future__ import annotations

from dataclasses import asdict, dataclass


COLOR_RED = "\x1b[31m"
COLOR_YELLOW = "\x1b[33m"
COLOR_GREEN = "\x1b[32m"
COLOR_RESET = "\x1b[0m"


@dataclass
class Issue:
    severity: str
    code: str
    message: str


@dataclass
class ValidationReport:
    issues: list[Issue]

    @property
    def failed(self) -> bool:
        return any(item.severity == "error" for item in self.issues)

    def summary_counts(self) -> dict[str, int]:
        counts = {"errors": 0, "warnings": 0, "passed": 0}
        for item in self.issues:
            if item.severity == "error":
                counts["errors"] += 1
            elif item.severity == "warning":
                counts["warnings"] += 1
            else:
                counts["passed"] += 1
        return counts

    def to_json(self) -> dict[str, object]:
        return {
            "ok": not self.failed,
            "issues": [asdict(i) for i in self.issues],
            "summary": self.summary_counts(),
        }


def format_text(report: ValidationReport) -> str:
    return format_text_with_options(report, use_color=False)


def _colorize(text: str, color: str, use_color: bool) -> str:
    if not use_color:
        return text
    return f"{color}{text}{COLOR_RESET}"


def format_text_with_options(report: ValidationReport, use_color: bool) -> str:
    lines: list[str] = []
    for issue in report.issues:
        severity = issue.severity.upper()
        label = f"[{severity}]"
        if issue.severity == "error":
            label = _colorize(label, COLOR_RED, use_color)
        elif issue.severity == "warning":
            label = _colorize(label, COLOR_YELLOW, use_color)
        elif issue.severity == "pass":
            label = _colorize(label, COLOR_GREEN, use_color)
        lines.append(f"{label} {issue.code}: {issue.message}")

    counts = report.summary_counts()
    summary = f"Summary: {counts['passed']} passed, {counts['warnings']} warnings, {counts['errors']} errors"
    if counts["errors"]:
        summary = _colorize(summary, COLOR_RED, use_color)
    elif counts["warnings"]:
        summary = _colorize(summary, COLOR_YELLOW, use_color)
    else:
        summary = _colorize(summary, COLOR_GREEN, use_color)
    lines.append(summary)
    return "\n".join(lines)
