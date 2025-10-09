# AutoTrader Documentation

This directory contains the source files for the AutoTrader documentation site, built with [MkDocs](https://www.mkdocs.org/) and the [Material theme](https://squidfunk.github.io/mkdocs-material/).

## Structure

```
docs/
├── index.md                  # Homepage
├── quickstart.md             # Quick start guide
├── installation.md           # Installation instructions
├── configuration.md          # Configuration overview
├── first-scan.md             # First scan tutorial
│
├── cli/                      # CLI reference (auto-generated)
│   ├── index.md              # CLI overview
│   ├── options.md            # All command-line options
│   ├── exit-codes.md         # Exit code reference
│   ├── environment.md        # Environment variables
│   └── examples.md           # CLI examples
│
├── config/                   # Configuration documentation
│   ├── index.md              # Config overview
│   ├── format.md             # YAML format reference
│   ├── sources.md            # Config sources (file/env/CLI)
│   ├── effective-config.md   # Debugging config with --print-effective-config
│   └── best-practices.md     # Configuration best practices
│
├── strategies/               # Strategy plugin documentation
│   ├── index.md              # Strategies overview
│   ├── plugin-api.md         # Plugin API reference
│   ├── writing-strategies.md # Strategy development guide
│   ├── examples.md           # Example strategies
│   └── api-versioning.md     # API versioning and compatibility
│
├── metrics/                  # Metrics documentation (auto-generated)
│   ├── registry.md           # Full metrics registry
│   ├── types.md              # Metric types (counter, gauge, etc.)
│   ├── validation.md         # Validation rules
│   ├── observability.md      # Observability setup
│   └── free-data-sources.md  # Free data sources
│
├── schema/                   # Schema documentation
│   ├── index.md              # Schema overview
│   ├── current.md            # Current schema version
│   ├── history.md            # Version history
│   └── migration.md          # Migration guides
│
├── reproducibility/          # Reproducibility documentation
│   ├── index.md              # Reproducibility overview
│   ├── stamp.md              # Reproducibility stamp format
│   ├── deterministic.md      # Deterministic mode
│   └── validation.md         # Validating reproducibility
│
├── operations/               # Operations documentation
│   ├── locking.md            # File locking and TTL
│   ├── concurrency.md        # Concurrency control
│   ├── errors.md             # Error handling
│   ├── logging.md            # Logging configuration
│   └── monitoring.md         # Monitoring and metrics
│
├── development/              # Development documentation
│   ├── release-checklist.md  # Release process
│   ├── changelog.md          # Changelog
│   ├── contributing.md       # Contributing guidelines
│   └── testing.md            # Testing guidelines
│
└── reference/                # Reference documentation
    ├── manpage.md            # Manual page (auto-generated)
    ├── api.md                # API documentation
    └── glossary.md           # Glossary of terms
```

## Auto-Generated Files

The following files are automatically generated and should NOT be edited manually:

- `cli/options.md` - Generated from argparse parser
- `cli/exit-codes.md` - Generated from exit code definitions
- `cli/environment.md` - Generated from environment variable list
- `cli/examples.md` - Generated from examples
- `metrics/registry.md` - Generated from `config/metrics_registry.yaml`
- `metrics/validation.md` - Generated from registry validation rules
- `reference/manpage.md` - Generated from manpage generator

To regenerate these files:

```bash
# Regenerate all documentation
make docs-gen

# Or individually
python scripts/gen_cli_docs.py
python scripts/gen_metrics_docs.py
python scripts/gen_manpage.py --format md --output docs/reference/manpage.md
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
python scripts/gen_all_docs.py

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
