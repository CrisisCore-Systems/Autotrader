.PHONY: backtest coverage sbom security

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
