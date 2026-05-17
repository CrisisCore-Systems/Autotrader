from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("UNKNOWN", re.compile(r"\bUNKNOWN\b", re.IGNORECASE)),
    ("AGPL", re.compile(r"\bAGPL\b", re.IGNORECASE)),
    ("LGPL", re.compile(r"\bLGPL\b|Lesser General Public License", re.IGNORECASE)),
    ("GPL", re.compile(r"\bGPL\b|General Public License", re.IGNORECASE)),
    ("MPL", re.compile(r"\bMPL\b|Mozilla Public License", re.IGNORECASE)),
    ("Zope", re.compile(r"\bZope\b", re.IGNORECASE)),
    ("CNRI", re.compile(r"\bCNRI\b", re.IGNORECASE)),
    ("complex expression", re.compile(r"\b(AND|OR)\b", re.IGNORECASE)),
    ("linking exception", re.compile(r"linking exception", re.IGNORECASE)),
]


def load_report(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Expected list JSON report at {path}")

    return [item for item in data if isinstance(item, dict)]


def field(item: dict[str, Any], *names: str) -> str:
    for name in names:
        value = item.get(name)
        if value is not None:
            return str(value)
    return ""


def classify(license_text: str) -> list[str]:
    matches: list[str] = []
    for label, pattern in SENSITIVE_PATTERNS:
        if pattern.search(license_text):
            matches.append(label)

    return matches


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def build_summary(lane: str, report: list[dict[str, Any]]) -> str:
    findings: list[tuple[str, str, str, str]] = []

    for item in report:
        name = field(item, "Name", "name")
        version = field(item, "Version", "version")
        license_text = field(item, "License", "license")
        categories = classify(license_text)

        if categories:
            findings.append((name, version, license_text, ", ".join(categories)))

    lines: list[str] = [
        f"# License warning summary for {lane} lane",
        "",
        "This report is warning-only. It does not fail the build.",
        "",
        f"Packages scanned: {len(report)}",
        f"Review-sensitive findings: {len(findings)}",
        "",
    ]

    if not findings:
        lines.extend([
            "No review-sensitive license findings detected.",
            "",
        ])
        return "\n".join(lines)

    lines.extend([
        "| Package | Version | License | Warning categories |",
        "|---|---:|---|---|",
    ])

    for name, version, license_text, categories in sorted(findings, key=lambda row: row[0].lower()):
        lines.append(
            f"| {markdown_escape(name)} | {markdown_escape(version)} | "
            f"{markdown_escape(license_text)} | {markdown_escape(categories)} |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate warning-only dependency lane license summary."
    )
    parser.add_argument("--lane", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)

    args = parser.parse_args()

    try:
        report = load_report(args.input)
        summary = build_summary(args.lane, report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(summary, encoding="utf-8")
        print(summary)
    except Exception as exc:
        fallback = (
            f"# License warning summary for {args.lane} lane\n\n"
            "This report is warning-only. It does not fail the build.\n\n"
            f"Reporter error captured for investigation: {exc}\n"
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(fallback, encoding="utf-8")
        print(fallback)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
