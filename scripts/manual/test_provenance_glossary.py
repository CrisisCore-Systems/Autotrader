"""Tests for provenance tracking and glossary generation."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timedelta
import pandas as pd
from src.core.features import MarketSnapshot
from src.core.safety import evaluate_contract
from src.core.provenance_tracking import complete_pipeline_tracked
from src.core.provenance import get_provenance_tracker, reset_provenance_tracker, ArtifactType
from src.core.glossary import get_glossary, TermCategory


def test_provenance_tracking():
    """Test provenance tracking functionality."""
    print("=" * 60)
    print("Testing Provenance Tracking")
    print("=" * 60)
    
    # Reset for clean test
    reset_provenance_tracker()
    tracker = get_provenance_tracker()
    
    # Create test data
    now = datetime.utcnow()
    dates = [now - timedelta(hours=i) for i in range(24)][::-1]
    prices = pd.Series(
        data=[0.1 + 0.001 * i for i in range(24)],
        index=pd.to_datetime(dates)
    )
    
    snapshot = MarketSnapshot(
        symbol="TEST",
        timestamp=now,
        price=float(prices.iloc[-1]),
        volume_24h=100000,
        liquidity_usd=200000,
        holders=1000,
        onchain_metrics={"active_wallets": 200},
        narratives=["DeFi", "Test"]
    )
    
    contract_report = evaluate_contract(
        {"honeypot": False, "owner_can_mint": False},
        severity="none"
    )
    
    # Run pipeline with tracking
    results = complete_pipeline_tracked(
        snapshot=snapshot,
        price_series=prices,
        narrative_embedding_score=0.8,
        contract_report=contract_report,
        data_source="test"
    )
    
    # Verify results
    assert 'result' in results
    assert 'provenance' in results
    assert results['result'].score > 0
    
    score_id = results['provenance']['score_id']
    
    # Test lineage
    lineage = tracker.get_lineage(score_id)
    print(f"✓ Lineage tracked: {len(lineage)} artifacts")
    assert len(lineage) > 0
    
    # Test record retrieval
    record = tracker.get_record(score_id)
    assert record is not None
    assert record.artifact.artifact_type == ArtifactType.GEM_SCORE
    print(f"✓ Record retrieved: {record.artifact.name}")
    
    # Test transformations
    assert len(record.transformations) > 0
    print(f"✓ Transformations tracked: {len(record.transformations)}")
    
    # Test quality metrics
    assert len(record.quality_metrics) > 0
    print(f"✓ Quality metrics recorded: {len(record.quality_metrics)}")
    
    # Test lineage export
    mermaid = tracker.export_lineage_graph(score_id, format="mermaid")
    assert "graph TD" in mermaid
    print(f"✓ Mermaid diagram generated: {len(mermaid)} chars")
    
    # Test statistics
    stats = tracker.get_statistics()
    assert stats['total_artifacts'] > 0
    print(f"✓ Statistics: {stats['total_artifacts']} artifacts, {stats['total_transformations']} transformations")
    
    print("\n✅ All provenance tests passed!\n")
    return True


def test_glossary():
    """Test glossary functionality."""
    print("=" * 60)
    print("Testing Glossary Generation")
    print("=" * 60)
    
    glossary = get_glossary()
    
    # Test term lookup
    gem_score = glossary.get_term("GemScore")
    assert gem_score is not None
    assert gem_score.category == TermCategory.SCORE
    print(f"✓ Term lookup: {gem_score.term}")
    
    # Test alias resolution
    rsi = glossary.get_term("RelativeStrengthIndex")
    assert rsi is not None
    assert rsi.term == "RSI"
    print(f"✓ Alias resolution: RelativeStrengthIndex -> {rsi.term}")
    
    # Test search
    risk_results = glossary.search("risk")
    assert len(risk_results) > 0
    print(f"✓ Search: Found {len(risk_results)} terms matching 'risk'")
    
    # Test category browsing
    metrics = glossary.get_by_category(TermCategory.METRIC)
    assert len(metrics) > 0
    print(f"✓ Category browsing: {len(metrics)} metrics")
    
    features = glossary.get_by_category(TermCategory.FEATURE)
    assert len(features) > 0
    print(f"✓ Feature count: {len(features)}")
    
    # Test custom term addition
    glossary.add_term(
        term="TestMetric",
        category=TermCategory.METRIC,
        definition="A test metric for validation",
        range=(0.0, 1.0),
        tags={"test"}
    )
    
    test_metric = glossary.get_term("TestMetric")
    assert test_metric is not None
    print(f"✓ Custom term added: {test_metric.term}")
    
    # Test statistics
    stats = glossary.get_statistics()
    assert stats['total_terms'] > 0
    print(f"✓ Statistics: {stats['total_terms']} terms, {stats['categories_count']} categories")
    
    # Test markdown generation
    markdown = glossary.export_markdown(include_toc=True, group_by_category=True)
    assert "# Technical Glossary" in markdown
    assert "GemScore" in markdown
    print(f"✓ Markdown export: {len(markdown)} chars")
    
    # Test JSON generation
    json_data = glossary.export_json()
    assert '"terms"' in json_data
    print(f"✓ JSON export: {len(json_data)} chars")
    
    # Test term markdown
    term_md = gem_score.to_markdown()
    assert "### GemScore" in term_md
    print(f"✓ Term markdown: {len(term_md)} chars")
    
    print("\n✅ All glossary tests passed!\n")
    return True


def test_integration():
    """Test integration between provenance and glossary."""
    print("=" * 60)
    print("Testing Integration")
    print("=" * 60)
    
    reset_provenance_tracker()
    tracker = get_provenance_tracker()
    glossary = get_glossary()
    
    # Create test data
    now = datetime.utcnow()
    dates = [now - timedelta(hours=i) for i in range(12)][::-1]
    prices = pd.Series(
        data=[0.5 + 0.01 * i for i in range(12)],
        index=pd.to_datetime(dates)
    )
    
    snapshot = MarketSnapshot(
        symbol="INTG",
        timestamp=now,
        price=0.61,
        volume_24h=50000,
        liquidity_usd=150000,
        holders=500,
        onchain_metrics={"active_wallets": 100},
        narratives=["Test"]
    )
    
    contract_report = evaluate_contract({}, "none")
    
    # Run pipeline
    results = complete_pipeline_tracked(
        snapshot=snapshot,
        price_series=prices,
        narrative_embedding_score=0.75,
        contract_report=contract_report,
        data_source="integration_test"
    )
    
    # Verify all features in result are documented in glossary
    features_found = 0
    features_missing = []
    
    for feature_name in results['features'].keys():
        term = glossary.get_term(feature_name)
        if term:
            features_found += 1
        else:
            features_missing.append(feature_name)
    
    print(f"✓ Features documented: {features_found}/{len(results['features'])}")
    
    if features_missing:
        print(f"⚠ Missing documentation for: {', '.join(features_missing[:3])}")
    
    # Verify provenance for each stage
    score_id = results['provenance']['score_id']
    lineage = tracker.get_lineage(score_id)
    
    expected_types = [
        ArtifactType.MARKET_SNAPSHOT,
        ArtifactType.PRICE_SERIES,
        ArtifactType.FEATURE_VECTOR,
        ArtifactType.GEM_SCORE
    ]
    
    types_found = set()
    for artifact_id in lineage:
        record = tracker.get_record(artifact_id)
        if record:
            types_found.add(record.artifact.artifact_type)
    
    for expected_type in expected_types:
        assert expected_type in types_found, f"Missing artifact type: {expected_type}"
    
    print(f"✓ All expected artifact types present")
    
    print("\n✅ Integration test passed!\n")
    return True


def test_export():
    """Test exporting documentation."""
    print("=" * 60)
    print("Testing Documentation Export")
    print("=" * 60)
    
    glossary = get_glossary()
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    
    # Export markdown
    md_path = docs_dir / "TEST_GLOSSARY.md"
    glossary.export_markdown(output_path=md_path)
    
    assert md_path.exists()
    content = md_path.read_text()
    assert "# Technical Glossary" in content
    print(f"✓ Glossary markdown exported: {md_path}")
    
    # Export JSON
    json_path = docs_dir / "test_glossary.json"
    glossary.export_json(output_path=json_path)
    
    assert json_path.exists()
    json_content = json_path.read_text()
    assert '"terms"' in json_content
    print(f"✓ Glossary JSON exported: {json_path}")
    
    # Test provenance export
    reset_provenance_tracker()
    tracker = get_provenance_tracker()
    
    artifact_id = tracker.register_artifact(
        artifact_type=ArtifactType.REPORT,
        name="Test Report",
        data={"test": True},
        tags={"test"}
    )
    
    graph_dict = tracker.export_lineage_graph(artifact_id, format="dict")
    assert "nodes" in graph_dict
    assert "edges" in graph_dict
    print(f"✓ Lineage graph exported as dict")
    
    # Cleanup test files
    md_path.unlink()
    json_path.unlink()
    print(f"✓ Test files cleaned up")
    
    print("\n✅ Export test passed!\n")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("PROVENANCE & GLOSSARY TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        ("Provenance Tracking", test_provenance_tracking),
        ("Glossary Generation", test_glossary),
        ("Integration", test_integration),
        ("Documentation Export", test_export),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 All tests passed successfully!\n")
    else:
        print(f"\n⚠️ {failed} test(s) failed\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
