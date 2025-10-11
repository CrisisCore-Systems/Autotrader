# Provenance & Glossary Quick Reference

Quick reference for artifact provenance tracking and glossary generation.

## Quick Start

### Provenance Tracking

```python
from src.core.provenance_tracking import complete_pipeline_tracked

# Run complete pipeline with tracking
results = complete_pipeline_tracked(
    snapshot=market_snapshot,
    price_series=price_data,
    narrative_embedding_score=0.75,
    contract_report=safety_report,
    data_source="etherscan"
)

# Access provenance
lineage = results['provenance']['lineage']
score_id = results['provenance']['score_id']
```

### Glossary

```python
from src.core.glossary import get_glossary

glossary = get_glossary()

# Look up term
term = glossary.get_term("GemScore")
print(term.definition)

# Search
results = glossary.search("risk")

# Export
glossary.export_markdown(Path("docs/GLOSSARY.md"))
```

---

## Common Patterns

### Pattern 1: Track Individual Artifacts

```python
from src.core.provenance import get_provenance_tracker, ArtifactType

tracker = get_provenance_tracker()

artifact_id = tracker.register_artifact(
    artifact_type=ArtifactType.FEATURE_VECTOR,
    name="Features[BTC]",
    data=features_dict,
    parent_ids=[parent_id],
    tags={"crypto", "features"}
)
```

### Pattern 2: Export Lineage Graph

```python
# Get Mermaid diagram
mermaid = tracker.export_lineage_graph(artifact_id, format="mermaid")

# Get JSON
json_graph = tracker.export_lineage_graph(artifact_id, format="json")
```

### Pattern 3: Add Custom Glossary Terms

```python
from src.core.glossary import TermCategory

glossary.add_term(
    term="CustomMetric",
    category=TermCategory.METRIC,
    definition="Your definition here",
    formula="x * y",
    range=(0.0, 1.0)
)
```

---

## Artifact Types

| Type | Description |
|------|-------------|
| `RAW_DATA` | Original external data |
| `MARKET_SNAPSHOT` | Normalized market data |
| `PRICE_SERIES` | Time series prices |
| `FEATURE_VECTOR` | Computed features |
| `GEM_SCORE` | Final scores |
| `CONTRACT_REPORT` | Safety analysis |
| `NARRATIVE_EMBEDDING` | Narrative analysis |
| `AGGREGATED_METRICS` | Aggregated data |
| `REPORT` | Generated reports |

---

## Transformation Types

| Type | Description |
|------|-------------|
| `INGESTION` | Data ingestion |
| `FEATURE_EXTRACTION` | Feature computation |
| `NORMALIZATION` | Normalize data |
| `AGGREGATION` | Aggregate data |
| `SCORING` | Score calculation |
| `PENALTY_APPLICATION` | Apply penalties |
| `FILTERING` | Filter data |
| `ENRICHMENT` | Enrich data |

---

## Term Categories

| Category | Description |
|----------|-------------|
| `METRIC` | Quantitative measurements |
| `FEATURE` | Computed features |
| `SCORE` | Scoring components |
| `INDICATOR` | Technical indicators |
| `CONCEPT` | Abstract concepts |
| `DATA_SOURCE` | External sources |
| `ALGORITHM` | Algorithms/methods |
| `RISK_FACTOR` | Risk factors |
| `ABBREVIATION` | Acronyms |

---

## Key Functions

### Provenance

```python
# Get tracker
tracker = get_provenance_tracker()

# Register
artifact_id = tracker.register_artifact(...)

# Query
record = tracker.get_record(artifact_id)
lineage = tracker.get_lineage(artifact_id)
descendants = tracker.get_descendants(artifact_id)

# Export
graph = tracker.export_lineage_graph(artifact_id, format="mermaid")
stats = tracker.get_statistics()
```

### Glossary

```python
# Get glossary
glossary = get_glossary()

# Lookup
term = glossary.get_term("TermName")

# Search
results = glossary.search("keyword")

# Browse
terms = glossary.get_by_category(TermCategory.METRIC)

# Export
glossary.export_markdown(path)
glossary.export_json(path)
```

---

## Cheat Sheet

### Complete Analysis with Tracking

```python
from src.core.provenance_tracking import complete_pipeline_tracked
from src.core.provenance import get_provenance_tracker

results = complete_pipeline_tracked(
    snapshot=snapshot,
    price_series=prices,
    narrative_embedding_score=0.7,
    contract_report=report,
    data_source="source"
)

tracker = get_provenance_tracker()
lineage = tracker.get_lineage(results['provenance']['score_id'])
```

### Export All Documentation

```python
from pathlib import Path
from src.core.glossary import get_glossary

glossary = get_glossary()
docs = Path("docs")

glossary.export_markdown(docs / "GLOSSARY.md")
glossary.export_json(docs / "glossary.json")
```

### View Statistics

```python
# Provenance stats
tracker_stats = tracker.get_statistics()
print(f"Artifacts: {tracker_stats['total_artifacts']}")

# Glossary stats
glossary_stats = glossary.get_statistics()
print(f"Terms: {glossary_stats['total_terms']}")
```

---

## Default Glossary Terms

Key terms available by default:

- **Scores**: GemScore, Confidence
- **Features**: SentimentScore, AccumulationScore, OnchainActivity, LiquidityDepth, TokenomicsRisk, ContractSafety, NarrativeMomentum, CommunityGrowth
- **Indicators**: RSI, MACD, Volatility, EMA
- **Metrics**: Recency, DataCompleteness
- **Concepts**: MarketSnapshot, FeatureVector, HiddenGem
- **Algorithms**: LiquidityGuardrail, PenaltyApplication
- **Data Sources**: Etherscan, DEXScreener

---

## Files

| File | Description |
|------|-------------|
| `src/core/provenance.py` | Core provenance system |
| `src/core/glossary.py` | Glossary generation |
| `src/core/provenance_tracking.py` | Pipeline integration |
| `../guides/PROVENANCE_GLOSSARY_GUIDE.md` | Full documentation |
| `notebooks/hidden_gem_scanner.ipynb` | Interactive examples |

---

**Quick Tip**: Run the notebook for interactive examples!

```bash
jupyter notebook notebooks/hidden_gem_scanner.ipynb
```
