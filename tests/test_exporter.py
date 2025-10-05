"""Tests for exporter service helpers."""

from __future__ import annotations

from pathlib import Path

from textwrap import dedent

from src.services.exporter import (
    render_html_artifact,
    render_markdown_artifact,
    save_artifact,
)


def test_render_markdown_artifact_handles_missing_fields() -> None:
    markdown = render_markdown_artifact({"title": "Test Artifact"})
    assert "Test Artifact" in markdown
    assert "# Lore" in markdown


def test_render_markdown_artifact_generates_dashboard_sections() -> None:
    payload = {
        "title": "Example",
        "timestamp": "2024-01-01T00:00:00Z",
        "glyph": "◇",
        "gem_score": 82.3456,
        "confidence": 0.91234,
        "flags": ["LiquidityFloorPass", "NoAnomalies"],
        "narrative_sentiment": "positive",
        "narrative_momentum": 0.4567,
        "price": 1.2345,
        "volume_24h": 987654.321,
        "liquidity": 54321.0,
        "holders": 1200,
        "features": {"Momentum": 0.9, "Risk": -0.3},
        "debug": {"threshold": 0.42},
        "narratives": ["Theme A", "Theme B"],
        "data_snapshot": ["Point 1", "Point 2"],
        "actions": ["Monitor exchange listings"],
        "news_items": [
            {
                "title": "Story",
                "summary": "A concise description of developments.",
                "link": "https://example.com/story",
                "source": "Feed",
                "published_at": "2024-01-01T00:00:00Z",
            }
        ],
    }

    markdown = render_markdown_artifact(payload)

    assert "# Executive Summary" in markdown
    assert "## Market Snapshot" in markdown
    assert "| Metric | Value |" in markdown
    assert "Momentum" in markdown  # feature table entry
    assert "## Diagnostics" in markdown
    assert "Theme A" in markdown
    assert "## News Highlights" in markdown
    assert "**Feed** — Story" in markdown
    assert "https://example.com/story" in markdown
    assert "# Data Snapshot" in markdown
    assert "Monitor exchange listings" in markdown


def test_render_markdown_artifact_deduplicates_flags_and_themes() -> None:
    payload = {
        "title": "Dedup",
        "flags": ["Repeat", "Repeat", "Unique"],
        "narratives": ["Echo", "Echo"],
    }

    markdown = render_markdown_artifact(payload)

    flag_block = dedent(
        """
        Flags:
          - Repeat
          - Unique
        """
    ).strip()
    assert flag_block in markdown
    assert "  - Echo" in markdown  # nested theme bullet retains indent


def test_render_markdown_artifact_limits_feature_table() -> None:
    payload = {
        "title": "Limiter",
        "features": {f"Metric {i}": i for i in range(15)},
    }

    markdown = render_markdown_artifact(payload)

    assert "…" in markdown  # ellipsis row indicates trimming
    assert markdown.count("Metric") <= 13  # 12 entries + ellipsis row


def test_render_html_artifact_contains_key_sections() -> None:
    payload = {
        "title": "Example",
        "timestamp": "2024-01-01T00:00:00Z",
        "glyph": "◇",
        "gem_score": 82.3456,
        "confidence": 0.91234,
        "flags": ["LiquidityFloorPass", "NoAnomalies"],
        "narrative_sentiment": "positive",
        "narrative_momentum": 0.4567,
        "price": 1.2345,
        "volume_24h": 987654.321,
        "liquidity": 54321.0,
        "holders": 1200,
        "features": {"Momentum": 0.9, "Risk": -0.3},
        "debug": {"threshold": 0.42},
        "narratives": ["Theme A", "Theme B"],
        "data_snapshot": ["Point 1", "Point 2"],
        "actions": ["Monitor exchange listings"],
        "lore": "Lore capsule",
        "news_items": [
            {
                "title": "Story",
                "summary": "A concise description of developments.",
                "link": "https://example.com/story",
                "source": "Feed",
                "published_at": "2024-01-01T00:00:00Z",
            }
        ],
    }

    html = render_html_artifact(payload)

    assert "<!DOCTYPE html>" in html
    assert "Executive Summary" in html
    assert "Market Snapshot" in html
    assert "Narrative Signals" in html
    assert "News Highlights" in html
    assert "Lore" in html
    assert "https://example.com/story" in html


def test_render_html_artifact_handles_missing_fields() -> None:
    html = render_html_artifact({"title": "Test Artifact"})
    assert "Test Artifact" in html
    assert "Executive Summary" in html


def test_save_artifact_writes_file(tmp_path: Path) -> None:
    path = save_artifact("content", tmp_path, "artifact.md")
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "content"
