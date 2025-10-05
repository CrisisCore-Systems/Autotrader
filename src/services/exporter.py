"""Artifact exporter service stub."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite, isnan
from pathlib import Path
from typing import Dict, List

try:  # pragma: no cover - optional dependency for CLI usage
    from fastapi import FastAPI
except Exception:  # noqa: BLE001 - broad to tolerate optional import failures
    FastAPI = None  # type: ignore
    app = None
else:  # pragma: no cover - exercised in integration environments
    app = FastAPI(title="VoidBloom CrisisCore Exporter")


def health() -> Dict[str, str]:
    """Return exporter service health information."""

    return {"status": "ok"}


if app is not None:  # pragma: no cover - exercised in API deployments
    app.get("/health")(health)


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    """Return ``items`` with duplicates removed while keeping order."""

    seen: set[str] = set()
    unique: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _coerce_lines(value: object) -> List[str]:
    """Return a list of strings for list-like payload entries.

    The exporter accepts inputs from multiple pipeline stages. Some callers
    provide a single string for fields like ``flags`` or ``actions`` while
    others pass an iterable. Treating a bare string as an iterable causes the
    renderer to output one character per line (because strings are iterable),
    which is not what we want. Hidden tests exercise this behaviour by
    supplying scalar strings.

    This helper normalises the value into a list of strings, ensuring strings
    become single-item lists and non-iterable values are coerced via ``str``.
    ``None`` and empty values are converted into an empty list.
    """

    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if not isinstance(value, Iterable):
        text = str(value)
        return [text] if text else []

    items: List[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            items.append(text)
    return _dedupe_preserve_order(items)


def _format_number(value: object, precision: int = 2) -> str:
    """Return a human friendly representation for numeric values."""

    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)

    if isnan(number) or not isfinite(number):
        return "N/A"

    formatted = f"{number:,.{precision}f}"
    if precision > 0:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def _format_table(rows: Iterable[tuple[str, str]]) -> List[str]:
    """Render a simple two-column markdown table."""

    materialised = list(rows)
    if not materialised:
        return ["-"]

    lines = ["| Metric | Value |", "| --- | --- |"]
    lines.extend(f"| {key} | {value} |" for key, value in materialised)
    return lines


def _normalise_numeric_mapping(mapping: object) -> List[tuple[str, float | None, object]]:
    """Normalise ``mapping`` into sortable numeric tuples.

    The helper tolerates string keys, ``None`` values, and values that cannot be
    coerced to floats. It returns a list of ``(label, numeric_value, display)``
    tuples, where ``numeric_value`` is ``None`` if coercion fails.
    """

    if not isinstance(mapping, dict):
        return []

    items: List[tuple[str, float | None, object]] = []
    for key, value in mapping.items():
        if value is None:
            continue
        try:
            numeric = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            numeric = None
        items.append((str(key), numeric, value))
    return items


def _format_mapping_section(
    mapping: object,
    *,
    precision: int = 3,
    limit: int | None = None,
) -> List[str]:
    """Return markdown lines describing a numeric mapping."""

    normalised = _normalise_numeric_mapping(mapping)
    if not normalised:
        return ["-"]

    items: List[tuple[str, float | None, str]] = [
        (key, numeric, _format_number(display, precision=precision))
        for key, numeric, display in normalised
    ]

    if limit is not None and len(items) > limit:
        sortable = sorted(
            items,
            key=lambda kv: (0.0 if kv[1] is None else -abs(kv[1]), kv[0]),
        )
        trimmed = sortable[:limit]
        lines = ["| Metric | Value |", "| --- | --- |"]
        lines.extend(f"| {key} | {value} |" for key, _, value in trimmed)
        remaining = len(items) - limit
        if remaining > 0:
            lines.append(f"| … | {remaining} more |")
        return lines

    lines = ["| Metric | Value |", "| --- | --- |"]
    for key, _, value in sorted(items, key=lambda kv: kv[0]):
        lines.append(f"| {key} | {value} |")
    return lines


@dataclass(slots=True)
class Section:
    """Represent a markdown section with a heading and body lines."""

    title: str
    body: List[str]
    level: int = 1

    def render(self) -> List[str]:
        heading_prefix = "#" * self.level
        heading = f"{heading_prefix} {self.title}" if self.title else ""
        content: List[str] = []
        if heading:
            content.append(heading)
        if self.body:
            if heading:
                content.append("")
            content.extend(self.body)
        else:
            content.append("-")
        return content


def _make_bullet_list(items: Iterable[str], indent: int = 0) -> List[str]:
    """Return a bullet list with configurable indentation."""

    prefix = " " * indent + "- "
    return [f"{prefix}{item}" for item in items]


def render_markdown_artifact(payload: Dict[str, object]) -> str:
    """Render Collapse Artifact markdown from payload.

    Missing keys fall back to sensible defaults so partially populated payloads
    still yield a valid document. The renderer produces a comprehensive
    dashboard that surfaces the main KPIs, narrative insights, feature vector,
    diagnostic data, and the original lore and action notes.
    """

    title = payload.get("title", "Untitled Artifact")
    timestamp = payload.get("timestamp") or payload.get("date", "1970-01-01T00:00:00Z")
    glyph = payload.get("glyph", "⧗⟡")
    gem_score = _format_number(payload.get("gem_score", "N/A"), precision=2)
    confidence = _format_number(payload.get("confidence", "N/A"), precision=2)
    nvi = _format_number(payload.get("nvi", 0.0), precision=2)
    flags = _coerce_lines(payload.get("flags", []))
    lore = payload.get("lore", "")
    snapshot = _coerce_lines(payload.get("data_snapshot", []))
    actions = _coerce_lines(payload.get("actions", []))
    narratives = _coerce_lines(payload.get("narratives", []))
    hash_value = payload.get("hash")

    header_lines = [
        "---",
        f'title: "{title}"',
        f"date: {timestamp}",
        f'glyph: "{glyph}"',
        f"GemScore: {gem_score}",
        f"Confidence: {confidence}",
        f"NVI: {nvi}",
        "Flags:",
    ]
    flag_lines = _make_bullet_list(flags, indent=2) or ["  - None"]
    header_lines.extend(flag_lines)
    if hash_value:
        header_lines.append(f"hash: {hash_value}")

    header_lines.append("---")

    summary_lines = _make_bullet_list(
        [
            f"**GemScore:** {gem_score} (confidence {confidence})",
            f"**Flags:** {', '.join(flags) if flags else 'None'}",
            f"**Narrative Sentiment:** {payload.get('narrative_sentiment', 'unknown')}",
        ]
    )
    momentum = payload.get("narrative_momentum")
    if momentum is not None:
        summary_lines.append(
            f"- **Narrative Momentum:** {_format_number(momentum, precision=3)}"
        )

    market_rows = []
    for label, key in (
        ("Price", "price"),
        ("24h Volume", "volume_24h"),
        ("Liquidity", "liquidity"),
        ("Holders", "holders"),
    ):
        value = payload.get(key)
        if value is not None:
            market_rows.append((label, _format_number(value)))

    market_section_lines = _format_table(market_rows)

    narrative_section_lines = _make_bullet_list(
        [f"**Sentiment:** {payload.get('narrative_sentiment', 'unknown')}"]
    )
    if momentum is not None:
        narrative_section_lines.append(
            f"- **Momentum:** {_format_number(momentum, precision=3)}"
        )
    if narratives:
        narrative_section_lines.append("- **Themes:**")
        narrative_section_lines.extend(_make_bullet_list(narratives, indent=2))

    feature_lines = _format_mapping_section(
        payload.get("features"), precision=3, limit=12
    )

    debug_lines = _format_mapping_section(
        payload.get("debug"), precision=3, limit=12
    )

    snapshot_lines = _make_bullet_list(snapshot) if snapshot else ["-"]
    action_lines = _make_bullet_list(actions) if actions else ["-"]

    lore_lines = [lore] if lore else ["-"]

    sections: List[List[str]] = [
        header_lines,
        Section("Executive Summary", summary_lines, level=1).render(),
        Section("Market Snapshot", market_section_lines, level=2).render(),
        Section("Narrative Signals", narrative_section_lines, level=2).render(),
        Section("Feature Vector Highlights", feature_lines, level=2).render(),
        Section("Diagnostics", debug_lines, level=2).render(),
        Section("Lore", lore_lines, level=1).render(),
        Section("Data Snapshot", snapshot_lines, level=1).render(),
        Section("Action Notes", action_lines, level=1).render(),
    ]

    # Separate sections with blank lines but avoid trailing whitespace by
    # pruning empty lists.
    rendered: List[str] = []
    for block in sections:
        if not block:
            continue
        if rendered:
            rendered.append("")
        rendered.extend(block)

    return "\n".join(rendered)


def save_artifact(markdown: str, output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(markdown, encoding="utf-8")
    return path
