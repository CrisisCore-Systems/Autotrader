# Artifact Provenance & Glossary Generation Guide

## Overview

This guide explains how to use the **Artifact Provenance Tracking** and **Glossary Generation** systems in the Hidden-Gem Scanner. These features provide:

- **Full Lineage Tracking**: Track the complete history and transformation of all data artifacts
- **Technical Documentation**: Automatically generate and maintain glossaries of metrics, features, and concepts
- **Quality Assurance**: Monitor data quality metrics and transformation performance
- **Reproducibility**: Understand exactly how any result was derived

## Table of Contents

1. [Artifact Provenance System](#artifact-provenance-system)
2. [Glossary Generation](#glossary-generation)
3. [Integration Examples](#integration-examples)
4. [Best Practices](#best-practices)
5. [API Reference](#api-reference)

---

## Artifact Provenance System

### What is Artifact Provenance?

Artifact provenance is the complete history of a data artifact, including:
- **Origins**: Where the data came from
- **Transformations**: What operations were applied
- **Lineage**: Parent and child artifacts
- **Quality Metrics**: Data quality measurements
- **Timing**: When artifacts were created and how long operations took

### Core Concepts

#### Artifact Types

```python
from src.core.provenance import ArtifactType

# Available types:
- RAW_DATA          # Original data from external sources
- MARKET_SNAPSHOT   # Normalized market data
- PRICE_SERIES      # Time series price data
- FEATURE_VECTOR    # Computed features
- GEM_SCORE         # Final scoring results
- CONTRACT_REPORT   # Smart contract analysis
- NARRATIVE_EMBEDDING  # Narrative analysis results
- AGGREGATED_METRICS   # Aggregated metrics
- REPORT            # Generated reports
```

#### Transformation Types

```python
from src.core.provenance import TransformationType

# Available types:
- INGESTION            # Data ingestion
- FEATURE_EXTRACTION   # Feature computation
- NORMALIZATION        # Data normalization
- AGGREGATION          # Data aggregation
- SCORING              # Score calculation
- PENALTY_APPLICATION  # Safety penalties
- FILTERING            # Data filtering
- ENRICHMENT           # Data enrichment
```

### Basic Usage

#### 1. Register an Artifact

```python
from src.core.provenance import get_provenance_tracker, ArtifactType

tracker = get_provenance_tracker()

artifact_id = tracker.register_artifact(
    artifact_type=ArtifactType.MARKET_SNAPSHOT,
    name="MarketSnapshot[BTC]",
    data=snapshot_data,
    data_source="etherscan",
    tags={"crypto", "ethereum"},
    custom_attributes={"symbol": "BTC", "price": 45000}
)
```

#### 2. Track Transformations

```python
from src.core.provenance import Transformation, TransformationType
import time

start = time.time()
# ... perform transformation ...
duration_ms = (time.time() - start) * 1000

transformation = Transformation(
    transformation_type=TransformationType.FEATURE_EXTRACTION,
    function_name="compute_features",
    parameters={"window": 24},
    duration_ms=duration_ms
)

tracker.add_transformation(artifact_id, transformation)
```

#### 3. Add Quality Metrics

```python
tracker.add_quality_metrics(
    artifact_id,
    {
        "completeness": 0.95,
        "accuracy": 0.88,
        "timeliness": 0.92
    }
)
```

#### 4. Query Lineage

```python
# Get complete ancestor lineage
lineage = tracker.get_lineage(artifact_id)

# Get descendants
descendants = tracker.get_descendants(artifact_id)

# Get specific record
record = tracker.get_record(artifact_id)
```

#### 5. Export Lineage Graph

```python
# Export as dictionary
graph_dict = tracker.export_lineage_graph(artifact_id, format="dict")

# Export as JSON
graph_json = tracker.export_lineage_graph(artifact_id, format="json")

# Export as Mermaid diagram
mermaid = tracker.export_lineage_graph(artifact_id, format="mermaid")
print(mermaid)
```

### Using Provenance-Tracked Pipeline

The easiest way to add provenance tracking is to use the pre-built wrapper functions:

```python
from src.core.provenance_tracking import complete_pipeline_tracked

results = complete_pipeline_tracked(
    snapshot=market_snapshot,
    price_series=price_data,
    narrative_embedding_score=0.75,
    contract_report=safety_report,
    data_source="dexscreener"
)

# Access results
gem_score = results['result']
features = results['features']
provenance_info = results['provenance']

# Get the complete lineage
lineage_ids = provenance_info['lineage']
```

### Provenance Record Structure

Each artifact has a complete provenance record:

```python
@dataclass
class ProvenanceRecord:
    artifact: ArtifactMetadata        # Core artifact metadata
    parent_artifacts: List[str]       # Parent artifact IDs
    transformations: List[Transformation]  # Applied transformations
    child_artifacts: List[str]        # Child artifact IDs
    data_sources: List[str]           # External data sources
    quality_metrics: Dict[str, float] # Quality measurements
    annotations: List[str]            # Human-readable notes
```

---

## Glossary Generation

### What is the Glossary System?

The glossary system automatically generates and maintains technical documentation for:
- Metrics and features
- Scoring components
- Technical indicators
- Risk factors
- Data sources
- Algorithms

### Core Concepts

#### Term Categories

```python
from src.core.glossary import TermCategory

- METRIC          # Quantitative measurements
- FEATURE         # Computed features
- SCORE           # Scoring components
- INDICATOR       # Technical indicators
- CONCEPT         # Abstract concepts
- DATA_SOURCE     # External data sources
- ALGORITHM       # Algorithms and methods
- RISK_FACTOR     # Risk assessment factors
- ABBREVIATION    # Acronyms and abbreviations
```

### Basic Usage

#### 1. Access Global Glossary

```python
from src.core.glossary import get_glossary

glossary = get_glossary()
```

#### 2. Look Up Terms

```python
# Get a term definition
term = glossary.get_term("GemScore")
print(term.definition)
print(term.formula)
print(term.range)

# Handle aliases
rsi_term = glossary.get_term("RelativeStrengthIndex")  # Returns RSI
```

#### 3. Search for Terms

```python
# Search by keyword
results = glossary.search("liquidity")

for term in results:
    print(f"{term.term}: {term.definition}")
```

#### 4. Browse by Category

```python
from src.core.glossary import TermCategory

# Get all metrics
metrics = glossary.get_by_category(TermCategory.METRIC)

# Get all risk factors
risks = glossary.get_by_category(TermCategory.RISK_FACTOR)
```

#### 5. Add Custom Terms

```python
from src.core.glossary import TermCategory

glossary.add_term(
    term="CustomMetric",
    category=TermCategory.METRIC,
    definition="Description of the custom metric",
    formula="x * y / z",
    range=(0.0, 1.0),
    unit="normalized",
    related_terms={"OtherMetric", "SomeFeature"},
    examples=["Example usage 1", "Example usage 2"]
)
```

#### 6. Export Documentation

```python
from pathlib import Path

# Export as Markdown
markdown = glossary.export_markdown(
    output_path=Path("docs/GLOSSARY.md"),
    include_toc=True,
    group_by_category=True
)

# Export as JSON
json_data = glossary.export_json(
    output_path=Path("docs/glossary.json")
)
```

### Glossary Term Structure

```python
@dataclass
class GlossaryTerm:
    term: str                        # Term name
    category: TermCategory           # Classification
    definition: str                  # Clear definition
    formula: Optional[str]           # Mathematical formula
    unit: Optional[str]              # Unit of measurement
    range: Optional[Tuple[float, float]]  # Valid range
    default_value: Optional[Any]     # Default value
    related_terms: Set[str]          # Related terms
    examples: List[str]              # Usage examples
    source_module: Optional[str]     # Source code module
    aliases: Set[str]                # Alternative names
    tags: Set[str]                   # Categorization tags
    version: str                     # Version tracking
    deprecated: bool                 # Deprecation status
```

### Automatic Extraction

The glossary can automatically extract terms from code:

```python
# Extract from weights dictionary
SCORING_WEIGHTS = {
    "SentimentScore": 0.15,
    "AccumulationScore": 0.20,
    # ...
}

glossary.extract_from_weights_dict(
    SCORING_WEIGHTS,
    category=TermCategory.FEATURE,
    source_module="src.core.scoring"
)

# Extract from dataclass
from dataclasses import dataclass

@dataclass
class MyMetrics:
    accuracy: float
    precision: float
    recall: float

glossary.extract_from_dataclass(
    MyMetrics,
    category=TermCategory.METRIC
)
```

---

## Integration Examples

### Example 1: Track a Complete Analysis

```python
from datetime import datetime
import pandas as pd
from src.core.features import MarketSnapshot
from src.core.provenance_tracking import complete_pipeline_tracked
from src.core.safety import evaluate_contract

# Prepare data
snapshot = MarketSnapshot(
    symbol="TOKEN",
    timestamp=datetime.utcnow(),
    price=1.50,
    volume_24h=100000,
    liquidity_usd=500000,
    holders=1000,
    onchain_metrics={"active_wallets": 200},
    narratives=["DeFi", "AI"]
)

prices = pd.Series([1.0, 1.1, 1.2, 1.3, 1.4, 1.5])
contract_report = evaluate_contract({}, "none")

# Run with full tracking
results = complete_pipeline_tracked(
    snapshot=snapshot,
    price_series=prices,
    narrative_embedding_score=0.8,
    contract_report=contract_report,
    data_source="etherscan"
)

# Access results
print(f"GemScore: {results['result'].score:.2f}")
print(f"Artifact lineage: {len(results['provenance']['lineage'])} steps")
```

### Example 2: Generate Custom Report with Provenance

```python
from src.core.provenance import get_provenance_tracker, ArtifactType

tracker = get_provenance_tracker()

# Create report artifact
report_id = tracker.register_artifact(
    artifact_type=ArtifactType.REPORT,
    name="Weekly Analysis Report",
    data={"symbols_analyzed": 50, "gems_found": 3},
    parent_ids=[score_id1, score_id2, score_id3],
    tags={"report", "weekly"},
    custom_attributes={"period": "2024-W42"}
)

# Add quality metrics
tracker.add_quality_metrics(report_id, {
    "coverage": 1.0,
    "confidence_avg": 0.85
})

# Add annotation
tracker.add_annotation(
    report_id,
    "Weekly report covering 50 tokens with 3 high-confidence gems identified"
)

# Export lineage
lineage_graph = tracker.export_lineage_graph(report_id, format="mermaid")
```

### Example 3: Maintain Custom Glossary

```python
from src.core.glossary import get_glossary, TermCategory

glossary = get_glossary()

# Add custom metrics for your strategy
glossary.add_term(
    term="WhaleActivityScore",
    category=TermCategory.FEATURE,
    definition="Normalized score measuring large wallet activity and accumulation patterns",
    formula="Σ(large_wallet_flows) / total_volume",
    range=(0.0, 1.0),
    related_terms={"AccumulationScore", "OnchainActivity"},
    examples=["Score > 0.7 indicates high whale activity"],
    tags={"custom", "onchain"}
)

# Export updated glossary
glossary.export_markdown(Path("docs/CUSTOM_GLOSSARY.md"))
```

---

## Best Practices

### Provenance Tracking

1. **Track at Source**: Register artifacts as soon as data enters your system
2. **Use Meaningful Names**: Make artifact names descriptive and include identifiers (e.g., symbol)
3. **Add Context**: Use tags and custom attributes to add searchable metadata
4. **Track Performance**: Always include duration_ms in transformations
5. **Quality Metrics**: Add quality metrics immediately after computing them
6. **Annotate Important Events**: Add human-readable annotations for key decisions

### Glossary Management

1. **Define Terms Early**: Add terms to the glossary as you introduce new concepts
2. **Include Examples**: Always provide usage examples for complex terms
3. **Link Related Terms**: Create connections between related concepts
4. **Version Tracking**: Use version fields when terms evolve
5. **Regular Exports**: Periodically export glossary to keep documentation current
6. **Deprecation**: Mark deprecated terms but don't delete them for backward compatibility

### Performance Considerations

1. **Batch Operations**: When tracking many artifacts, consider batching operations
2. **Selective Tracking**: For high-frequency operations, track samples rather than every instance
3. **Cleanup**: Implement cleanup policies for old provenance records if needed
4. **Export Frequency**: Export lineage graphs on-demand rather than continuously

---

## API Reference

### Provenance API

#### ProvenanceTracker

```python
tracker = get_provenance_tracker()

# Register artifact
artifact_id = tracker.register_artifact(...)

# Add transformation
tracker.add_transformation(artifact_id, transformation)

# Add quality metrics
tracker.add_quality_metrics(artifact_id, metrics_dict)

# Add annotation
tracker.add_annotation(artifact_id, text)

# Query
record = tracker.get_record(artifact_id)
lineage = tracker.get_lineage(artifact_id, depth=-1)
descendants = tracker.get_descendants(artifact_id)

# Export
graph = tracker.export_lineage_graph(artifact_id, format="dict|json|mermaid")
stats = tracker.get_statistics()
```

#### Provenance Tracking Wrappers

```python
from src.core.provenance_tracking import (
    track_market_snapshot,
    track_price_series,
    compute_time_series_features_tracked,
    build_feature_vector_tracked,
    apply_penalties_tracked,
    compute_gem_score_tracked,
    complete_pipeline_tracked
)
```

### Glossary API

#### GlossaryBuilder

```python
glossary = get_glossary()

# Add term
term = glossary.add_term(term, category, definition, **kwargs)

# Lookup
term = glossary.get_term(term_name)

# Search
results = glossary.search(query, case_sensitive=False)

# Browse
terms = glossary.get_by_category(category)

# Export
markdown = glossary.export_markdown(output_path, include_toc=True, group_by_category=True)
json_data = glossary.export_json(output_path)

# Statistics
stats = glossary.get_statistics()
```

---

## Example Workflows

### Workflow 1: Production Pipeline with Tracking

```python
# Initialize
from src.core.provenance import reset_provenance_tracker
reset_provenance_tracker()

# Run analysis
results = complete_pipeline_tracked(
    snapshot=data,
    price_series=prices,
    narrative_embedding_score=0.7,
    contract_report=report,
    data_source="production"
)

# Store provenance in database
tracker = get_provenance_tracker()
for artifact_id in results['provenance']['lineage']:
    record = tracker.get_record(artifact_id)
    db.store_provenance(record.to_dict())
```

### Workflow 2: Documentation Generation

```python
# Update glossary with new terms
glossary = get_glossary()
glossary.extract_from_weights_dict(NEW_WEIGHTS, ...)

# Export all documentation
from pathlib import Path
docs_dir = Path("docs")

glossary.export_markdown(docs_dir / "GLOSSARY.md")
glossary.export_json(docs_dir / "glossary.json")

# Generate term markdown for each category
for category in TermCategory:
    terms = glossary.get_by_category(category)
    if terms:
        output = f"# {category.value.title()}\n\n"
        for term in terms:
            output += term.to_markdown() + "\n\n"
        (docs_dir / f"{category.value}.md").write_text(output)
```

---

## Troubleshooting

### Common Issues

**Issue**: Artifact IDs not found
- **Solution**: Ensure artifacts are registered before querying

**Issue**: Lineage graph too large
- **Solution**: Use depth parameter to limit traversal

**Issue**: Memory usage growing
- **Solution**: Implement periodic cleanup or use reset_provenance_tracker()

**Issue**: Term not found in glossary
- **Solution**: Check for aliases using get_term()

---

## Further Reading

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [notebooks/hidden_gem_scanner.ipynb](notebooks/hidden_gem_scanner.ipynb) - Interactive examples
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick reference guide

---

## Contributing

To add new provenance features or glossary terms:

1. Define new artifact types in `src/core/provenance.py`
2. Add transformation types for new operations
3. Update `create_default_glossary()` in `src/core/glossary.py`
4. Export updated documentation

---

**Version**: 1.0.0  
**Last Updated**: 2024-10-08  
**Maintainer**: CrisisCore Systems
