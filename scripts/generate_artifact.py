#!/usr/bin/env python3
"""
Enhanced artifact generator with provenance tracking and secure templating.
Uses Jinja2 for safe template rendering with CSP headers.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import jinja2
import jsonschema
import yaml

# Configure Jinja2 with autoescaping for security
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("artifacts/templates"),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


class ArtifactGenerator:
    """Generate artifacts with comprehensive provenance tracking."""

    def __init__(
        self,
        artifact_type: str,
        template_name: str,
        output_path: Path,
        classification: str = "internal",
    ):
        self.artifact_type = artifact_type
        self.template_name = template_name
        self.output_path = output_path
        self.classification = classification
        self.generation_id = str(uuid.uuid4())
        self.generated_at = datetime.utcnow()

        # Load schemas
        self.metadata_schema = self._load_metadata_schema()

    def _load_metadata_schema(self) -> Dict[str, Any]:
        """Load artifact metadata JSON schema."""
        schema_path = Path("schemas/artifact_metadata.json")
        with open(schema_path) as f:
            return json.load(f)

    def _get_git_commit(self) -> str:
        """Get current git commit SHA."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()[:7]
        except subprocess.CalledProcessError:
            return "unknown"

    def _get_dependencies(self) -> Dict[str, Any]:
        """Capture runtime dependencies."""
        try:
            import sys
            import pkg_resources

            packages = {
                pkg.key: pkg.version
                for pkg in pkg_resources.working_set
            }

            return {
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "packages": packages,
            }
        except Exception:
            return {}

    def _compute_sha256(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def generate_metadata(
        self,
        input_window: Optional[Dict[str, Any]] = None,
        model_info: Optional[Dict[str, Any]] = None,
        feature_set: Optional[Dict[str, Any]] = None,
        data_sources: Optional[list] = None,
        retention_days: int = 90,
        tags: Optional[list] = None,
        custom: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate comprehensive artifact metadata.
        
        Args:
            input_window: Time window of input data
            model_info: LLM model information
            feature_set: Feature set used
            data_sources: External data sources
            retention_days: How long to retain artifact
            tags: Searchable tags
            custom: Custom metadata fields
            
        Returns:
            Validated metadata dictionary
        """
        metadata = {
            "schema_version": "1.0.0",
            "artifact_type": self.artifact_type,
            "generation_id": self.generation_id,
            "generated_at": self.generated_at.isoformat() + "Z",
            "source_commit": self._get_git_commit(),
            "generator_version": "2.0.0",
            "classification": self.classification,
        }

        # Optional fields
        if input_window:
            metadata["input_window"] = input_window

        if model_info:
            metadata["model_info"] = model_info

        if feature_set:
            metadata["feature_set"] = feature_set

        if data_sources:
            metadata["data_sources"] = data_sources

        # Retention
        expires_at = self.generated_at + timedelta(days=retention_days)
        metadata["retention"] = {
            "expires_at": expires_at.isoformat() + "Z",
            "retention_days": retention_days,
            "policy": f"auto_delete_{retention_days}d",
        }

        # Dependencies
        metadata["dependencies"] = self._get_dependencies()

        # Provenance trail
        metadata["provenance_trail"] = [
            {
                "step": "initialization",
                "timestamp": self.generated_at.isoformat() + "Z",
                "actor": "artifact_generator",
                "action": "created_metadata",
            }
        ]

        # Tags
        if tags:
            metadata["tags"] = tags

        # Custom metadata
        if custom:
            metadata["custom_metadata"] = custom

        # Validate against schema
        jsonschema.validate(metadata, self.metadata_schema)

        return metadata

    def render_template(
        self,
        context: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> str:
        """Render Jinja2 template with context and metadata.
        
        Args:
            context: Template context variables
            metadata: Artifact metadata
            
        Returns:
            Rendered template string
        """
        # Load template
        template = jinja_env.get_template(self.template_name)

        # Add metadata to context
        full_context = {
            **context,
            "__metadata": metadata,
            "__csp": self._generate_csp_header(),
        }

        # Render with safe escaping
        return template.render(**full_context)

    def _generate_csp_header(self) -> str:
        """Generate Content Security Policy header for HTML artifacts."""
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self';"
        )

    def save_artifact(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> Path:
        """Save artifact with embedded metadata.
        
        Args:
            content: Rendered artifact content
            metadata: Artifact metadata
            
        Returns:
            Path to saved artifact
        """
        # Compute checksums
        content_hash = self._compute_sha256(content)
        metadata["checksums"] = {
            "artifact_sha256": content_hash,
        }

        # Embed metadata based on artifact type
        if self.output_path.suffix == ".html":
            full_content = self._embed_html_metadata(content, metadata)
        elif self.output_path.suffix == ".md":
            full_content = self._embed_markdown_metadata(content, metadata)
        elif self.output_path.suffix == ".json":
            full_content = self._embed_json_metadata(content, metadata)
        else:
            # Fallback: JSON sidecar
            full_content = content
            self._save_sidecar_metadata(metadata)

        # Compute full hash
        full_hash = self._compute_sha256(full_content)
        metadata["checksums"]["full_sha256"] = full_hash

        # Write artifact
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(full_content, encoding="utf-8")

        return self.output_path

    def _embed_html_metadata(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Embed metadata in HTML as JSON-LD."""
        metadata_script = f"""
<script type="application/ld+json" id="artifact-metadata">
{json.dumps(metadata, indent=2)}
</script>
"""
        # Insert before </head> or at start if no head
        if "</head>" in content:
            return content.replace("</head>", f"{metadata_script}</head>")
        else:
            return metadata_script + content

    def _embed_markdown_metadata(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Embed metadata in Markdown front matter."""
        yaml_metadata = yaml.dump(metadata, default_flow_style=False)
        return f"---\n{yaml_metadata}---\n\n{content}"

    def _embed_json_metadata(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Wrap JSON content with metadata."""
        content_obj = json.loads(content)
        wrapped = {
            "__metadata": metadata,
            "content": content_obj,
        }
        return json.dumps(wrapped, indent=2)

    def _save_sidecar_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save metadata as sidecar JSON file."""
        sidecar_path = self.output_path.with_suffix(
            self.output_path.suffix + ".meta.json"
        )
        sidecar_path.write_text(json.dumps(metadata, indent=2))


def main():
    """Example usage."""
    generator = ArtifactGenerator(
        artifact_type="dashboard",
        template_name="dashboard.html.j2",
        output_path=Path("artifacts/dashboard.html"),
        classification="internal",
    )

    metadata = generator.generate_metadata(
        input_window={
            "start": "2025-10-01T00:00:00Z",
            "end": "2025-10-09T00:00:00Z",
            "duration_hours": 192,
        },
        model_info={
            "model_name": "gpt-4-turbo",
            "provider": "openai",
            "route": "narrative_summary",
        },
        tags=["dashboard", "daily", "gems"],
        retention_days=90,
    )

    context = {
        "title": "Hidden Gem Scanner Dashboard",
        "scan_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "tokens": [],
    }

    rendered = generator.render_template(context, metadata)
    output_path = generator.save_artifact(rendered, metadata)

    print(f"✅ Artifact generated: {output_path}")
    print(f"   Generation ID: {generator.generation_id}")
    print(f"   Metadata: {output_path}.meta.json")


if __name__ == "__main__":
    main()
