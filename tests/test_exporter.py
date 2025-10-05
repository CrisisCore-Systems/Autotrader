"""Tests for exporter service helpers."""

from __future__ import annotations

from pathlib import Path

from src.services.exporter import render_markdown_artifact, save_artifact


def test_render_markdown_artifact_handles_missing_fields() -> None:
    markdown = render_markdown_artifact({"title": "Test Artifact"})
    assert "Test Artifact" in markdown
    assert "# Lore" in markdown


def test_save_artifact_writes_file(tmp_path: Path) -> None:
    path = save_artifact("content", tmp_path, "artifact.md")
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "content"
