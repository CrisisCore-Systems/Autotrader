# AutoTrader Documentation

This directory contains the source files for the AutoTrader documentation site, built with [MkDocs](https://www.mkdocs.org/) and the [Material theme](https://squidfunk.github.io/mkdocs-material/).

For a curated map of the most important guides, open the new [Documentation Portal](documentation_portal.md). Keep it updated whenever new major docs land.

## Structure

```
docs/
├── index.md                    # MkDocs homepage
├── documentation_portal.md     # Consolidated navigation hub
├── ALERTING_V2_GUIDE.md        # Alerting v2 design and rollout guide
├── CLI_BACKTEST_GUIDE.md       # CLI backtest quick start
├── DRIFT_MONITORING_GUIDE.md   # Drift monitoring strategy
├── EXTENDED_BACKTEST_METRICS.md# Advanced performance metrics
├── FEATURE_STATUS.md           # Live feature tracker
├── IMPLEMENTATION_SUMMARY.md   # High-level implementation recap
├── OBSERVABILITY_GUIDE.md      # Observability playbook
├── QUICKSTART_NEW_SIGNALS.md   # Add/remove token workflow
├── RELIABILITY_IMPLEMENTATION.md # Reliability patterns overview
├── ROADMAP_COMPLETION_SUMMARY.md # Program roadmap updates
├── alerting/...
├── deployment/...
├── features/...
├── improvements/...
├── install/...
├── llm/...
├── metrics/...
├── observability/...
├── overview/...
├── quickref/...
└── status/...
```

## Auto-Generated Files

> **Heads up:** documentation generators were relocated to `scripts/docs/`. The legacy
> `scripts/*.py` entry points remain as shims for backward compatibility, but new
> automation should invoke the files under `scripts/docs/` directly.

The following files are automatically generated and should NOT be edited manually:

- `metrics/registry.md` – generated from `config/metrics_registry.yaml`
- `metrics/validation.md` – generated from metrics validation rules

To regenerate these files:

```bash
# Regenerate metrics documentation
python scripts/docs/gen_metrics_docs.py
```

## Building Documentation

### Local Development

```bash
# Generate auto-generated content and start dev server
make docs-serve

# Visit http://localhost:8000
```

### Production Build

```bash
# Generate auto-generated content and build static site
make docs-build

# Output in site/ directory
```

### Manual Commands

```bash
# Just generate auto-generated content
python scripts/docs/gen_all_docs.py

# Serve without regenerating
mkdocs serve

# Build without regenerating
mkdocs build
```

## Adding New Pages

1. Create a new `.md` file in the appropriate directory
2. Add it to the `nav` section in `mkdocs.yml`
3. Use Material for MkDocs features:
   - [Admonitions](https://squidfunk.github.io/mkdocs-material/reference/admonitions/)
   - [Code blocks](https://squidfunk.github.io/mkdocs-material/reference/code-blocks/)
   - [Tables](https://squidfunk.github.io/mkdocs-material/reference/data-tables/)
   - [Tabs](https://squidfunk.github.io/mkdocs-material/reference/content-tabs/)

### Example Page

```markdown
# Page Title

Brief introduction to the topic.

## Section

Content here.

!!! note "Important Note"
    This is an admonition block.

### Code Example

\```python
# Python code with syntax highlighting
from src.cli import manpage

generator = manpage.ManpageGenerator(parser)
output = generator.generate(format="man")
\```

### Table

| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |
```

## Writing Guidelines

1. **Be concise**: Get to the point quickly
2. **Use examples**: Show, don't just tell
3. **Link internally**: Use `[text](path.md)` for internal links
4. **Use admonitions**: Highlight important information with `!!! note`, `!!! warning`, etc.
5. **Test code**: Ensure all code examples actually work
6. **Check links**: Run `mkdocs build --strict` to catch broken links

## Styling

Custom CSS is in `docs/stylesheets/extra.css`. Custom JavaScript is in `docs/javascripts/`.

## Deployment

Documentation is automatically deployed to GitHub Pages on push to `main` branch (if configured).

Manual deployment:

```bash
# Build and deploy to gh-pages branch
mkdocs gh-deploy
```

## Dependencies

Install documentation dependencies:

```bash
pip install mkdocs mkdocs-material mkdocs-git-revision-date-localized-plugin mkdocs-minify-plugin
```

Or from requirements:

```bash
pip install -r requirements-docs.txt
```

## Troubleshooting

### "Page not found" errors

- Check that the file path in `nav` matches the actual file location
- Ensure `.md` extension is included in file paths (not in nav)

### Auto-generated content not updating

```bash
# Force regeneration
rm -rf docs/cli/*.md docs/metrics/*.md
make docs-gen
```

### Build fails with "strict mode" errors

- Fix broken internal links
- Ensure all referenced pages exist
- Check that all navigation items have valid targets

## Contributing

When contributing documentation:

1. Follow the existing structure
2. Use Material for MkDocs features for consistency
3. Test locally with `make docs-serve`
4. Ensure auto-generated files are not committed
5. Run `mkdocs build --strict` before submitting PR

---

**Last Updated**: 2025-10-08
