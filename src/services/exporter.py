"""Artifact exporter service stub."""

from __future__ import annotations

from pathlib import Path
from typing import Dict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from html import escape
from math import isfinite, isnan
from pathlib import Path
from typing import Dict, List

from src.security.artifact_integrity import get_signer

try:  # pragma: no cover - optional dependency for CLI usage
    from fastapi import FastAPI
except Exception:  # noqa: BLE001 - broad to tolerate optional import failures
    FastAPI = None  # type: ignore
    app = None
else:  # pragma: no cover - exercised in integration environments
    app = FastAPI(title="CrisisCore AutoTrader Exporter")


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

    rows = _mapping_rows(mapping, precision=precision, limit=limit)
    if not rows:
        return ["-"]

    lines = ["| Metric | Value |", "| --- | --- |"]
    lines.extend(f"| {label} | {value} |" for label, value in rows)
    return lines


def _mapping_rows(
    mapping: object,
    *,
    precision: int = 3,
    limit: int | None = None,
) -> List[tuple[str, str]]:
    """Return formatted rows for mapping-style metrics."""

    normalised = _normalise_numeric_mapping(mapping)
    if not normalised:
        return []

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
        rows = [(key, value) for key, _, value in trimmed]
        remaining = len(items) - limit
        if remaining > 0:
            rows.append(("…", f"{remaining} more"))
        return rows

    return [(key, value) for key, _, value in sorted(items, key=lambda kv: kv[0])]


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


def _truncate(text: str, *, limit: int = 240) -> str:
    clean = (text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def _format_news_section(items: Sequence[Mapping[str, object]]) -> List[str]:
    if not items:
        return ["- None"]

    lines: List[str] = []
    for item in items:
        source = str(item.get("source") or "News")
        title = str(item.get("title") or "Update")
        published = item.get("published_at")
        header = f"**{source}** — {title}"
        if published:
            header += f" ({published})"
        lines.append(f"- {header}")

        summary = item.get("summary")
        if summary:
            lines.append(f"  - {_truncate(str(summary))}")

        link = item.get("link")
        if link:
            lines.append(f"  - {link}")

    return lines


def _format_news_section_html(items: Sequence[Mapping[str, object]]) -> str:
    """Return HTML for the news section."""

    if not items:
        return "<p class=\"muted\">- None</p>"

    fragments: List[str] = ["<ul class=\"news-list\">"]
    for item in items:
        source = escape(str(item.get("source") or "News"))
        title = escape(str(item.get("title") or "Update"))
        published = item.get("published_at")
        header = f"<strong>{source}</strong> — {title}"
        if published:
            header += f" <span class=\"muted\">({escape(str(published))})</span>"

        fragments.append("  <li><article>")
        fragments.append(f"    <h4>{header}</h4>")

        summary = item.get("summary")
        if summary:
            fragments.append(f"    <p>{escape(_truncate(str(summary)))}</p>")

        link = item.get("link")
        if link:
            href = escape(str(link), quote=True)
            fragments.append(f'    <p><a href="{href}">{href}</a></p>')

        fragments.append("  </article></li>")

    fragments.append("</ul>")
    return "\n".join(fragments)


def _render_table_html(rows: Sequence[tuple[str, str]]) -> str:
    if not rows:
        return "<p class=\"muted\">-</p>"

    fragments = [
        "<table>",
        "  <thead><tr><th>Metric</th><th>Value</th></tr></thead>",
        "  <tbody>",
    ]
    for label, value in rows:
        fragments.append(
            f"    <tr><td>{escape(label)}</td><td>{escape(value)}</td></tr>"
        )
    fragments.append("  </tbody>")
    fragments.append("</table>")
    return "\n".join(fragments)


def _render_list_html(items: Sequence[str]) -> str:
    if not items:
        return "<p class=\"muted\">-</p>"

    fragments = ["<ul>"]
    for item in items:
        fragments.append(f"  <li>{escape(item)}</li>")
    fragments.append("</ul>")
    return "\n".join(fragments)


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
    final_score = _format_number(payload.get("final_score", "N/A"), precision=2)
    nvi = _format_number(payload.get("nvi", 0.0), precision=2)
    flags = _coerce_lines(payload.get("flags", []))
    lore = payload.get("lore", "")
    snapshot = _coerce_lines(payload.get("data_snapshot", []))
    actions = _coerce_lines(payload.get("actions", []))
    narratives = _coerce_lines(payload.get("narratives", []))
    hash_value = payload.get("hash")
    news_section_lines = _format_news_section(payload.get("news_items", []))
    sentiment_metric_lines = _format_mapping_section(payload.get("sentiment_metrics"), precision=3)
    technical_metric_lines = _format_mapping_section(payload.get("technical_metrics"), precision=3)
    security_metric_lines = _format_mapping_section(payload.get("security_metrics"), precision=3)

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
    flag_lines = [f"  - {flag}" for flag in flags]
    header_lines.extend(flag_lines)

    # Use full implementation with all sections including news
    momentum = payload.get("narrative_momentum")
    sentiment = payload.get("narrative_sentiment", "unknown")

    market_rows = [
        ("Price", payload.get("price")),
        ("24h Volume", payload.get("volume_24h")),
        ("Liquidity", payload.get("liquidity")),
        ("Holders", payload.get("holders")),
    ]
    market_rows = [
        (label, _format_number(value))
        for label, value in market_rows
        if value is not None
    ]

    summary_lines = [
        f"GemScore: {gem_score} (confidence {confidence})",
        f"Final Score: {final_score}",
        f"Flags: {', '.join(flags) if flags else 'None'}",
        f"Narrative Sentiment: {sentiment}",
    ]
    if momentum is not None:
        summary_lines.append(f"Narrative Momentum: {_format_number(momentum, precision=3)}")

    market_section_lines = _format_table(market_rows)

    narrative_section_lines = _make_bullet_list(
        [f"**Sentiment:** {sentiment}"]
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
        Section("Sentiment Metrics", sentiment_metric_lines, level=2).render(),
        Section("Technical Metrics", technical_metric_lines, level=2).render(),
        Section("Security Metrics", security_metric_lines, level=2).render(),
        Section("News Highlights", news_section_lines, level=2).render(),
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

    template = "\n".join(rendered)
    
    # Sign the artifact with cryptographic signature
    signer = get_signer()
    signature = signer.sign_artifact(template, metadata={
        "title": title,
        "timestamp": timestamp,
        "type": "markdown_artifact"
    })
    
    # Append signature section
    template += "\n\n---\n\n# Artifact Signature\n\n"
    template += f"**Hash Algorithm:** {signature.hash_algorithm}\n\n"
    template += f"**Content Hash (SHA-256):**\n```\n{signature.content_hash}\n```\n\n"
    template += f"**HMAC Signature:**\n```\n{signature.hmac_signature}\n```\n\n"
    template += f"**Signed At:** {signature.timestamp}\n"

    return template


def render_html_artifact(payload: Dict[str, object]) -> str:
    """Render a styled HTML dashboard for the Collapse Artifact payload."""

    title = str(payload.get("title", "Untitled Artifact"))
    timestamp = str(payload.get("timestamp") or payload.get("date", "1970-01-01T00:00:00Z"))
    glyph = str(payload.get("glyph", "⧗⟡"))
    gem_score = _format_number(payload.get("gem_score", "N/A"), precision=2)
    confidence = _format_number(payload.get("confidence", "N/A"), precision=2)
    final_score = _format_number(payload.get("final_score", "N/A"), precision=2)
    nvi = _format_number(payload.get("nvi", 0.0), precision=2)
    sentiment = str(payload.get("narrative_sentiment", "unknown"))
    momentum = payload.get("narrative_momentum")
    flags = _coerce_lines(payload.get("flags", []))
    narratives = _coerce_lines(payload.get("narratives", []))
    snapshot = _coerce_lines(payload.get("data_snapshot", []))
    actions = _coerce_lines(payload.get("actions", []))
    lore = str(payload.get("lore", ""))
    news_items = payload.get("news_items", [])
    hash_value = payload.get("hash")

    market_rows = [
        ("Price", payload.get("price")),
        ("24h Volume", payload.get("volume_24h")),
        ("Liquidity", payload.get("liquidity")),
        ("Holders", payload.get("holders")),
    ]
    market_rows = [
        (label, _format_number(value))
        for label, value in market_rows
        if value is not None
    ]

    feature_rows = _mapping_rows(payload.get("features"), precision=3, limit=12)
    debug_rows = _mapping_rows(payload.get("debug"), precision=3, limit=12)
    sentiment_rows = _mapping_rows(payload.get("sentiment_metrics"), precision=3, limit=12)
    technical_rows = _mapping_rows(payload.get("technical_metrics"), precision=3, limit=12)
    security_rows = _mapping_rows(payload.get("security_metrics"), precision=3, limit=12)

    summary_items = [
        f"GemScore: {gem_score} (confidence {confidence})",
        f"Final Score: {final_score}",
        f"Flags: {', '.join(flags) if flags else 'None'}",
        f"Narrative Sentiment: {sentiment}",
    ]
    if momentum is not None:
        summary_items.append(
            f"Narrative Momentum: {_format_number(momentum, precision=3)}"
        )

    flag_badges = (
        "".join(f"<span class=\"flag\">{escape(flag)}</span>" for flag in flags)
        if flags
        else "<span class=\"muted\">None</span>"
    )

    css = """
body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: #0d1117; color: #f0f6fc; }
main { padding: 2rem; max-width: 960px; margin: 0 auto; }
header.artifact-header { background: linear-gradient(135deg, rgba(56,139,253,0.35), rgba(139,92,246,0.35)); padding: 2rem; border-bottom: 1px solid rgba(240,246,252,0.1); }
header.artifact-header h1 { margin: 0; font-size: 2rem; }
header.artifact-header p { margin: 0.25rem 0 0; color: rgba(240,246,252,0.8); }
section { margin-top: 2rem; background: rgba(13,17,23,0.85); border: 1px solid rgba(240,246,252,0.08); border-radius: 12px; box-shadow: 0 20px 45px rgba(2,6,23,0.45); overflow: hidden; }
section h2 { margin: 0; padding: 1rem 1.5rem; background: rgba(240,246,252,0.04); border-bottom: 1px solid rgba(240,246,252,0.06); font-size: 1.2rem; }
section .content { padding: 1.25rem 1.5rem; }
table { width: 100%; border-collapse: collapse; margin: 0; }
table th, table td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid rgba(240,246,252,0.08); }
table th { text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.75rem; color: rgba(240,246,252,0.6); }
table tr:last-child td { border-bottom: none; }
ul { margin: 0; padding-left: 1.25rem; }
.muted { color: rgba(240,246,252,0.6); }
.flag { display: inline-block; padding: 0.25rem 0.6rem; margin: 0.15rem; border-radius: 999px; background: rgba(56,139,253,0.2); border: 1px solid rgba(56,139,253,0.45); font-size: 0.75rem; letter-spacing: 0.04em; text-transform: uppercase; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem 1.5rem; margin-bottom: 1rem; }
.summary-grid p { margin: 0; }
.news-list { list-style: none; padding-left: 0; }
.news-list > li { margin-bottom: 1.25rem; }
.news-list h4 { margin: 0 0 0.35rem; font-size: 1rem; }
.news-list p { margin: 0.25rem 0; }
a { color: #58a6ff; }
pre { white-space: pre-wrap; }
""".strip()

    news_html = _format_news_section_html(news_items)

    # Prepare momentum display value
    momentum_display = (
        escape(_format_number(momentum, precision=3))
        if momentum is not None
        else '<span class="muted">N/A</span>'
    )
    
    sections = [
        (
            "Executive Summary",
            "\n".join(
                [
                    "<div class=\"summary-grid\">",
                    f"  <p><strong>GemScore:</strong> {escape(gem_score)}</p>",
                    f"  <p><strong>Confidence:</strong> {escape(confidence)}</p>",
                    f"  <p><strong>Final Score:</strong> {escape(final_score)}</p>",
                    f"  <p><strong>NVI:</strong> {escape(nvi)}</p>",
                    f"  <p><strong>Flags:</strong> {flag_badges}</p>",
                    f"  <p><strong>Sentiment:</strong> {escape(sentiment)}</p>",
                    f"  <p><strong>Momentum:</strong> {momentum_display}</p>",
                    "</div>",
                    _render_list_html(summary_items),
                ]
            ),
        ),
        ("Market Snapshot", _render_table_html(market_rows)),
        (
            "Narrative Signals",
            "\n".join(
                [
                    f"<p><strong>Sentiment:</strong> {escape(sentiment)}</p>",
                    (
                        f"<p><strong>Momentum:</strong> {escape(_format_number(momentum, precision=3))}</p>"
                        if momentum is not None
                        else "<p class=\"muted\">Momentum unavailable</p>"
                    ),
                    "<div class=\"themes\">",
                    _render_list_html(narratives),
                    "</div>",
                ]
            ),
        ),
        ("Sentiment Metrics", _render_table_html(sentiment_rows)),
        ("Technical Metrics", _render_table_html(technical_rows)),
        ("Security Metrics", _render_table_html(security_rows)),
        ("News Highlights", news_html),
        ("Feature Vector Highlights", _render_table_html(feature_rows)),
        ("Diagnostics", _render_table_html(debug_rows)),
        ("Lore", f"<pre>{escape(lore) if lore else '-'}</pre>"),
        ("Data Snapshot", _render_list_html(snapshot)),
        ("Action Notes", _render_list_html(actions)),
    ]

    # Build HTML content first (without signature section)
    body_fragments = ["<main>"]
    for title_text, content in sections:
        body_fragments.append("  <section>")
        body_fragments.append(f"    <h2>{escape(title_text)}</h2>")
        body_fragments.append("    <div class=\"content\">")
        body_fragments.append(content)
        body_fragments.append("    </div>")
        body_fragments.append("  </section>")
    body_fragments.append("</main>")

    html_content = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8" />',
        f"<title>{escape(title)}</title>",
        f"<style>{css}</style>",
        "</head>",
        "<body>",
        "<header class=\"artifact-header\">",
        f"  <h1>{escape(glyph)} {escape(title)}</h1>",
        f"  <p>{escape(timestamp)}</p>",
        "</header>",
        *body_fragments,
        "</body>",
        "</html>",
    ]
    
    html_string = "\n".join(html_content)
    
    # Sign the complete HTML artifact
    signer = get_signer()
    signature = signer.sign_artifact(html_string, metadata={
        "title": title,
        "timestamp": timestamp,
        "type": "html_artifact"
    })
    
    # Insert signature section before closing body tag
    signature_section = [
        "  <section class=\"signature-section\">",
        "    <h2>🔐 Artifact Signature</h2>",
        "    <div class=\"content\">",
        f"      <p><strong>Hash Algorithm:</strong> {escape(signature.hash_algorithm)}</p>",
        f"      <p><strong>Content Hash (SHA-256):</strong></p>",
        f"      <pre style=\"font-size: 0.85em; overflow-wrap: break-word;\">{escape(signature.content_hash)}</pre>",
        f"      <p><strong>HMAC Signature:</strong></p>",
        f"      <pre style=\"font-size: 0.85em; overflow-wrap: break-word;\">{escape(signature.hmac_signature)}</pre>",
        f"      <p><strong>Signed At:</strong> {escape(signature.timestamp)}</p>",
        f"      <p class=\"muted\" style=\"font-size: 0.9em; margin-top: 1rem;\">This cryptographic signature ensures the integrity of this artifact. Any tampering will be detected during verification.</p>",
        "    </div>",
        "  </section>",
    ]
    
    # Insert signature before </body></html>
    final_html = html_string.replace("</body>", "\n".join(signature_section) + "\n</body>")
    
    return final_html


def save_artifact(markdown: str, output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(markdown, encoding="utf-8")
    return path
