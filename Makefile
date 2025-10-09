.PHONY: backtest coverage sbom security manpage manpage-md docs docs-serve docs-build test-repro test-manpage test-all

backtest:
	python -m pipeline.backtest --start 2023-01-01 --end 2025-09-30 --k 10 --walk 30d

coverage:
	pytest --cov=src --cov-report=term-missing

sbom:
	syft packages . -o cyclonedx-json=sbom.json

security:
	pip-audit
	semgrep --config auto
	bandit -r src -ll

manpage:
	python scripts/gen_manpage.py --format man --output dist/autotrader-scan.1

manpage-md:
	python scripts/gen_manpage.py --format md --output docs/man/autotrader-scan.md

docs-gen:
	@echo "Generating documentation..."
	python scripts/gen_all_docs.py

docs-serve: docs-gen
	@echo "Starting documentation server..."
	mkdocs serve

docs-build: docs-gen
	@echo "Building documentation site..."
	mkdocs build

docs: docs-build

test-repro:
	@echo "Running reproducibility integration tests..."
	pytest tests/test_reproducibility_integration.py -v

test-manpage:
	@echo "Running manpage generation tests..."
	pytest tests/test_manpage_generation.py -v

test-all: test-manpage test-repro
	@echo "All technical debt resolution tests completed!"
