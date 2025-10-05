"""Artifact exporter service stub."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

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


def render_markdown_artifact(payload: Dict[str, str]) -> str:
    """Render Collapse Artifact markdown from payload.

    Missing keys fall back to sensible defaults so that partially populated
    payloads still yield a valid artifact document. This mirrors the behaviour
    of the dashboard exporter which progressively enriches the payload as more
    data arrives.
    """

    title = payload.get("title", "Untitled Artifact")
    date = payload.get("date", "1970-01-01T00:00:00Z")
    glyph = payload.get("glyph", "⧗⟡")
    gem_score = payload.get("gem_score", "N/A")
    confidence = payload.get("confidence", "N/A")
    nvi = payload.get("nvi", 0.0)
    flags = payload.get("flags", []) or []
    lore = payload.get("lore", "")
    snapshot = payload.get("data_snapshot", []) or []
    actions = payload.get("actions", []) or []

    header_lines = [
        "---",
        f'title: "{title}"',
        f"date: {date}",
        f'glyph: "{glyph}"',
        f"GemScore: {gem_score}",
        f"Confidence: {confidence}",
        f"NVI: {nvi}",
        "Flags:",
    ]
    flag_lines = [f"  - {flag}" for flag in flags]

    template = "\n".join(header_lines + flag_lines + ["---", "", "# Lore", lore, "", "# Data Snapshot"])
    if snapshot:
        template += "\n" + "\n".join(f"- {item}" for item in snapshot)
    else:
        template += "\n-"

    template += "\n\n# Action Notes"
    if actions:
        template += "\n" + "\n".join(f"- {note}" for note in actions)
    else:
        template += "\n-"

    return template


def save_artifact(markdown: str, output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(markdown, encoding="utf-8")
    return path
