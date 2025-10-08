"""Quick example demonstrating provenance tracking and glossary usage."""

from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

from src.core.features import MarketSnapshot
from src.core.safety import evaluate_contract
from src.core.provenance_tracking import complete_pipeline_tracked
from src.core.provenance import get_provenance_tracker
from src.core.glossary import get_glossary


def main():
    """Run a quick demo of provenance and glossary features."""
    
    print("=" * 70)
    print("PROVENANCE & GLOSSARY QUICK DEMO")
    print("=" * 70)
    
    # Create sample data
    print("\n1. Creating sample data...")
    now = datetime.utcnow()
    dates = [now - timedelta(hours=i) for i in range(24)][::-1]
    prices = pd.Series(
        data=[0.5 + 0.01 * i for i in range(24)],
        index=pd.to_datetime(dates)
    )
    
    snapshot = MarketSnapshot(
        symbol="DEMO",
        timestamp=now,
        price=float(prices.iloc[-1]),
        volume_24h=500000,
        liquidity_usd=750000,
        holders=2500,
        onchain_metrics={
            "active_wallets": 500,
            "net_inflows": 200000,
            "unlock_pressure": 0.15
        },
        narratives=["DeFi", "Gaming"]
    )
    
    contract_report = evaluate_contract(
        {"honeypot": False, "owner_can_mint": False},
        severity="none"
    )
    
    print(f"   ✓ Created data for {snapshot.symbol}")
    
    # Run analysis with provenance tracking
    print("\n2. Running analysis with provenance tracking...")
    results = complete_pipeline_tracked(
        snapshot=snapshot,
        price_series=prices,
        narrative_embedding_score=0.8,
        contract_report=contract_report,
        data_source="demo"
    )
    
    gem_score = results['result']
    print(f"   ✓ GemScore: {gem_score.score:.2f}")
    print(f"   ✓ Confidence: {gem_score.confidence:.2f}%")
    print(f"   ✓ Flagged: {results['flagged']}")
    
    # Explore provenance
    print("\n3. Exploring provenance...")
    tracker = get_provenance_tracker()
    score_id = results['provenance']['score_id']
    
    lineage = tracker.get_lineage(score_id)
    print(f"   ✓ Lineage tracked: {len(lineage)} artifacts")
    
    # Show artifact chain
    print("\n   Artifact Chain:")
    for i, artifact_id in enumerate(lineage[-5:], 1):  # Show last 5
        record = tracker.get_record(artifact_id)
        if record:
            print(f"     {i}. {record.artifact.artifact_type.value}: {record.artifact.name}")
    
    # Get statistics
    stats = tracker.get_statistics()
    print(f"\n   ✓ Total artifacts: {stats['total_artifacts']}")
    print(f"   ✓ Transformations: {stats['total_transformations']}")
    
    # Export lineage as Mermaid
    print("\n4. Exporting lineage diagram...")
    mermaid = tracker.export_lineage_graph(score_id, format="mermaid")
    print(f"   ✓ Generated Mermaid diagram ({len(mermaid)} chars)")
    print("\n   Preview (first 200 chars):")
    print("   " + mermaid[:200].replace("\n", "\n   "))
    
    # Use glossary
    print("\n5. Using glossary...")
    glossary = get_glossary()
    
    # Look up key terms
    key_terms = ["GemScore", "RSI", "ContractSafety"]
    print("\n   Key Terms:")
    for term_name in key_terms:
        term = glossary.get_term(term_name)
        if term:
            definition = term.definition[:80] + "..." if len(term.definition) > 80 else term.definition
            print(f"   - {term.term}: {definition}")
    
    # Search
    print("\n   Searching for 'liquidity'...")
    search_results = glossary.search("liquidity")
    print(f"   ✓ Found {len(search_results)} terms")
    for term in search_results[:3]:
        print(f"     - {term.term} ({term.category.value})")
    
    # Get statistics
    glossary_stats = glossary.get_statistics()
    print(f"\n   ✓ Total terms: {glossary_stats['total_terms']}")
    print(f"   ✓ Categories: {glossary_stats['categories_count']}")
    
    # Export documentation
    print("\n6. Exporting documentation...")
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    
    # Export glossary
    glossary_path = docs_dir / "DEMO_GLOSSARY.md"
    glossary.export_markdown(output_path=glossary_path)
    print(f"   ✓ Glossary exported: {glossary_path}")
    
    # Export JSON
    json_path = docs_dir / "demo_glossary.json"
    glossary.export_json(output_path=json_path)
    print(f"   ✓ JSON exported: {json_path}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"""
Analysis Results:
  • Symbol: {snapshot.symbol}
  • GemScore: {gem_score.score:.2f}
  • Confidence: {gem_score.confidence:.2f}%
  • Flagged: {results['flagged']}

Provenance:
  • Artifacts tracked: {len(lineage)}
  • Transformations: {stats['total_transformations']}
  • Data source: demo

Documentation:
  • Glossary terms: {glossary_stats['total_terms']}
  • Exported to: {glossary_path}

Next Steps:
  1. View lineage at: https://mermaid.live (paste Mermaid diagram)
  2. Read glossary: {glossary_path}
  3. Explore notebook: notebooks/hidden_gem_scanner.ipynb
    """)
    
    print("=" * 70)
    print("✅ Demo complete!")
    print("=" * 70)
    
    # Cleanup demo files
    if glossary_path.exists():
        glossary_path.unlink()
    if json_path.exists():
        json_path.unlink()
    print("\n(Demo files cleaned up)")


if __name__ == "__main__":
    main()
