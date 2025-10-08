"""Glossary generation for technical terms and metrics.

This module provides automatic extraction and documentation of technical
terms, metrics, features, and concepts used throughout the system.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path


class TermCategory(Enum):
    """Categories of glossary terms."""
    
    METRIC = "metric"
    FEATURE = "feature"
    SCORE = "score"
    INDICATOR = "indicator"
    CONCEPT = "concept"
    DATA_SOURCE = "data_source"
    ALGORITHM = "algorithm"
    RISK_FACTOR = "risk_factor"
    ABBREVIATION = "abbreviation"


@dataclass
class GlossaryTerm:
    """Represents a single glossary term with metadata."""
    
    term: str
    category: TermCategory
    definition: str
    formula: Optional[str] = None
    unit: Optional[str] = None
    range: Optional[Tuple[float, float]] = None
    default_value: Optional[Any] = None
    related_terms: Set[str] = field(default_factory=set)
    examples: List[str] = field(default_factory=list)
    source_module: Optional[str] = None
    aliases: Set[str] = field(default_factory=set)
    tags: Set[str] = field(default_factory=set)
    version: str = "1.0.0"
    deprecated: bool = False
    deprecation_note: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "term": self.term,
            "category": self.category.value,
            "definition": self.definition,
            "formula": self.formula,
            "unit": self.unit,
            "range": self.range,
            "default_value": self.default_value,
            "related_terms": list(self.related_terms),
            "examples": self.examples,
            "source_module": self.source_module,
            "aliases": list(self.aliases),
            "tags": list(self.tags),
            "version": self.version,
            "deprecated": self.deprecated,
            "deprecation_note": self.deprecation_note,
        }
    
    def to_markdown(self) -> str:
        """Convert to Markdown format."""
        lines = [f"### {self.term}"]
        
        if self.deprecated:
            lines.append(f"\n**⚠️ DEPRECATED**: {self.deprecation_note or 'This term is deprecated.'}")
        
        lines.append(f"\n**Category**: {self.category.value.title()}")
        
        if self.aliases:
            lines.append(f"**Aliases**: {', '.join(sorted(self.aliases))}")
        
        lines.append(f"\n{self.definition}")
        
        if self.formula:
            lines.append(f"\n**Formula**: `{self.formula}`")
        
        if self.unit:
            lines.append(f"**Unit**: {self.unit}")
        
        if self.range:
            lines.append(f"**Range**: [{self.range[0]}, {self.range[1]}]")
        
        if self.default_value is not None:
            lines.append(f"**Default Value**: `{self.default_value}`")
        
        if self.examples:
            lines.append("\n**Examples**:")
            for example in self.examples:
                lines.append(f"- {example}")
        
        if self.related_terms:
            lines.append(f"\n**Related Terms**: {', '.join(sorted(self.related_terms))}")
        
        if self.source_module:
            lines.append(f"\n*Source: `{self.source_module}`*")
        
        return "\n".join(lines)


class GlossaryBuilder:
    """Builder for creating and managing technical glossaries."""
    
    def __init__(self):
        """Initialize the glossary builder."""
        self.terms: Dict[str, GlossaryTerm] = {}
        self.aliases: Dict[str, str] = {}  # alias -> canonical term
        self.categories: Dict[TermCategory, Set[str]] = {cat: set() for cat in TermCategory}
        
    def add_term(
        self,
        term: str,
        category: TermCategory,
        definition: str,
        **kwargs,
    ) -> GlossaryTerm:
        """Add a term to the glossary.
        
        Parameters
        ----------
        term : str
            The term to define.
        category : TermCategory
            Category classification.
        definition : str
            Clear definition of the term.
        **kwargs
            Additional term attributes (formula, unit, range, etc.).
            
        Returns
        -------
        GlossaryTerm
            The created term object.
        """
        glossary_term = GlossaryTerm(
            term=term,
            category=category,
            definition=definition,
            **kwargs,
        )
        
        self.terms[term] = glossary_term
        self.categories[category].add(term)
        
        # Register aliases
        if "aliases" in kwargs:
            for alias in kwargs["aliases"]:
                self.aliases[alias] = term
        
        return glossary_term
    
    def get_term(self, term: str) -> Optional[GlossaryTerm]:
        """Get a term definition, resolving aliases if needed."""
        # Check if it's an alias
        canonical = self.aliases.get(term, term)
        return self.terms.get(canonical)
    
    def get_by_category(self, category: TermCategory) -> List[GlossaryTerm]:
        """Get all terms in a specific category."""
        term_names = self.categories.get(category, set())
        return [self.terms[name] for name in sorted(term_names)]
    
    def search(self, query: str, case_sensitive: bool = False) -> List[GlossaryTerm]:
        """Search for terms matching a query string."""
        results = []
        
        if not case_sensitive:
            query = query.lower()
        
        for term_obj in self.terms.values():
            term_text = term_obj.term if case_sensitive else term_obj.term.lower()
            definition_text = term_obj.definition if case_sensitive else term_obj.definition.lower()
            
            if query in term_text or query in definition_text:
                results.append(term_obj)
        
        return results
    
    def add_related_terms(self, term: str, related: Set[str]) -> None:
        """Add related terms to an existing term."""
        if term in self.terms:
            self.terms[term].related_terms.update(related)
    
    def extract_from_weights_dict(
        self,
        weights: Dict[str, float],
        category: TermCategory = TermCategory.FEATURE,
        source_module: Optional[str] = None,
    ) -> None:
        """Extract terms from a weights dictionary (e.g., scoring weights).
        
        Parameters
        ----------
        weights : Dict[str, float]
            Dictionary mapping feature names to weights.
        category : TermCategory
            Category to assign to extracted terms.
        source_module : Optional[str]
            Source module name for reference.
        """
        for feature_name, weight in weights.items():
            if feature_name not in self.terms:
                # Generate basic definition from name
                definition = self._generate_definition_from_name(feature_name)
                
                self.add_term(
                    term=feature_name,
                    category=category,
                    definition=definition,
                    default_value=weight,
                    source_module=source_module,
                    tags={"auto_extracted", "weight"},
                )
    
    def extract_from_dataclass(
        self,
        dataclass_type: type,
        category: TermCategory = TermCategory.CONCEPT,
    ) -> None:
        """Extract terms from a dataclass definition.
        
        Parameters
        ----------
        dataclass_type : type
            The dataclass to extract fields from.
        category : TermCategory
            Category to assign to extracted terms.
        """
        if not hasattr(dataclass_type, "__dataclass_fields__"):
            return
        
        for field_name, field_obj in dataclass_type.__dataclass_fields__.items():
            if field_name not in self.terms:
                # Extract definition from docstring or generate
                definition = self._extract_field_definition(dataclass_type, field_name)
                
                self.add_term(
                    term=field_name,
                    category=category,
                    definition=definition,
                    source_module=dataclass_type.__module__,
                    tags={"auto_extracted", "dataclass_field"},
                )
    
    def _generate_definition_from_name(self, name: str) -> str:
        """Generate a basic definition from a camelCase or snake_case name."""
        # Convert CamelCase to words
        words = re.sub(r'([A-Z])', r' \1', name).split()
        # Convert snake_case to words
        words = [w for word in words for w in word.split('_')]
        # Filter empty strings and capitalize
        words = [w.capitalize() for w in words if w]
        
        if not words:
            return f"The {name} metric or feature."
        
        return f"{' '.join(words)} metric used in the analysis."
    
    def _extract_field_definition(self, dataclass_type: type, field_name: str) -> str:
        """Extract field definition from dataclass docstring."""
        docstring = inspect.getdoc(dataclass_type)
        
        if docstring:
            # Look for field documentation
            pattern = rf"{field_name}\s*:\s*(.+?)(?:\n|$)"
            match = re.search(pattern, docstring)
            if match:
                return match.group(1).strip()
        
        return self._generate_definition_from_name(field_name)
    
    def export_markdown(
        self,
        output_path: Optional[Path] = None,
        include_toc: bool = True,
        group_by_category: bool = True,
    ) -> str:
        """Export glossary as Markdown document.
        
        Parameters
        ----------
        output_path : Optional[Path]
            Path to write the markdown file to.
        include_toc : bool
            Whether to include a table of contents.
        group_by_category : bool
            Whether to group terms by category.
            
        Returns
        -------
        str
            The generated markdown content.
        """
        lines = ["# Technical Glossary", ""]
        lines.append("Comprehensive glossary of technical terms, metrics, and concepts used in the Hidden-Gem Scanner.")
        lines.append("")
        
        # Add statistics
        stats = self.get_statistics()
        lines.append("## Overview")
        lines.append(f"- **Total Terms**: {stats['total_terms']}")
        lines.append(f"- **Categories**: {stats['categories_count']}")
        lines.append("")
        
        if include_toc:
            lines.append("## Table of Contents")
            if group_by_category:
                for category in TermCategory:
                    terms_in_cat = self.categories.get(category, set())
                    if terms_in_cat:
                        lines.append(f"- [{category.value.title()}](#{category.value})")
            lines.append("")
        
        # Add terms
        if group_by_category:
            for category in TermCategory:
                terms = self.get_by_category(category)
                if terms:
                    lines.append(f"## {category.value.title()}")
                    lines.append("")
                    for term in terms:
                        lines.append(term.to_markdown())
                        lines.append("")
        else:
            lines.append("## Terms (Alphabetical)")
            lines.append("")
            for term_name in sorted(self.terms.keys()):
                lines.append(self.terms[term_name].to_markdown())
                lines.append("")
        
        markdown_content = "\n".join(lines)
        
        if output_path:
            output_path.write_text(markdown_content, encoding="utf-8")
        
        return markdown_content
    
    def export_json(self, output_path: Optional[Path] = None) -> str:
        """Export glossary as JSON."""
        import json
        
        data = {
            "terms": [term.to_dict() for term in self.terms.values()],
            "statistics": self.get_statistics(),
        }
        
        json_content = json.dumps(data, indent=2)
        
        if output_path:
            output_path.write_text(json_content, encoding="utf-8")
        
        return json_content
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the glossary."""
        deprecated_count = sum(1 for term in self.terms.values() if term.deprecated)
        
        category_counts = {
            cat.value: len(terms)
            for cat, terms in self.categories.items()
            if terms
        }
        
        return {
            "total_terms": len(self.terms),
            "categories_count": len([c for c, t in self.categories.items() if t]),
            "category_breakdown": category_counts,
            "deprecated_terms": deprecated_count,
            "total_aliases": len(self.aliases),
        }


def create_default_glossary() -> GlossaryBuilder:
    """Create a glossary with default terms for the Hidden-Gem Scanner."""
    glossary = GlossaryBuilder()
    
    # Scoring features
    glossary.add_term(
        term="GemScore",
        category=TermCategory.SCORE,
        definition="Composite score (0-100) quantifying a token's potential as a hidden gem, based on weighted features.",
        formula="Σ(weight_i × feature_i) × 100",
        range=(0.0, 100.0),
        source_module="src.core.scoring",
        related_terms={"SentimentScore", "AccumulationScore", "Confidence"},
        examples=["GemScore of 85 indicates high potential", "Threshold is typically 70"],
    )
    
    glossary.add_term(
        term="SentimentScore",
        category=TermCategory.FEATURE,
        definition="Normalized sentiment derived from news articles, social media, and community discussions.",
        range=(0.0, 1.0),
        unit="normalized",
        source_module="src.core.scoring",
        related_terms={"NarrativeMomentum", "CommunityGrowth"},
    )
    
    glossary.add_term(
        term="AccumulationScore",
        category=TermCategory.FEATURE,
        definition="Measures whether tokens are being accumulated by holders or distributed, based on wallet flows.",
        range=(0.0, 1.0),
        source_module="src.core.scoring",
        related_terms={"OnchainActivity"},
    )
    
    glossary.add_term(
        term="OnchainActivity",
        category=TermCategory.FEATURE,
        definition="Composite metric of blockchain activity including active wallets, transaction volume, and network usage.",
        range=(0.0, 1.0),
        source_module="src.core.scoring",
        related_terms={"AccumulationScore"},
    )
    
    glossary.add_term(
        term="LiquidityDepth",
        category=TermCategory.FEATURE,
        definition="Normalized measure of available liquidity in USD across trading venues.",
        range=(0.0, 1.0),
        unit="normalized",
        source_module="src.core.scoring",
        related_terms={"TokenomicsRisk"},
    )
    
    glossary.add_term(
        term="TokenomicsRisk",
        category=TermCategory.RISK_FACTOR,
        definition="Risk score based on token distribution, vesting schedules, and unlock pressure.",
        range=(0.0, 1.0),
        source_module="src.core.scoring",
        related_terms={"LiquidityDepth", "ContractSafety"},
    )
    
    glossary.add_term(
        term="ContractSafety",
        category=TermCategory.RISK_FACTOR,
        definition="Safety score from smart contract analysis including honeypot checks, ownership risks, and verification status.",
        range=(0.0, 1.0),
        source_module="src.core.safety",
        related_terms={"TokenomicsRisk"},
    )
    
    glossary.add_term(
        term="NarrativeMomentum",
        category=TermCategory.FEATURE,
        definition="Measures how strongly a token aligns with trending narratives and market themes.",
        range=(0.0, 1.0),
        source_module="src.core.scoring",
        related_terms={"SentimentScore"},
    )
    
    glossary.add_term(
        term="CommunityGrowth",
        category=TermCategory.FEATURE,
        definition="Rate of growth in community metrics such as holders, social followers, and engagement.",
        range=(0.0, 1.0),
        source_module="src.core.scoring",
        related_terms={"SentimentScore"},
    )
    
    glossary.add_term(
        term="Confidence",
        category=TermCategory.METRIC,
        definition="Confidence level (0-100) in the GemScore calculation, based on data recency and completeness.",
        formula="0.5 × Recency + 0.5 × DataCompleteness",
        range=(0.0, 100.0),
        source_module="src.core.scoring",
        related_terms={"GemScore", "Recency", "DataCompleteness"},
    )
    
    glossary.add_term(
        term="Recency",
        category=TermCategory.METRIC,
        definition="Score indicating how recent the data is, with higher values for more current information.",
        range=(0.0, 1.0),
        source_module="src.core.scoring",
        related_terms={"Confidence", "DataCompleteness"},
    )
    
    glossary.add_term(
        term="DataCompleteness",
        category=TermCategory.METRIC,
        definition="Fraction of required data fields that are available and valid for analysis.",
        range=(0.0, 1.0),
        source_module="src.core.scoring",
        related_terms={"Confidence", "Recency"},
    )
    
    # Technical indicators
    glossary.add_term(
        term="RSI",
        category=TermCategory.INDICATOR,
        definition="Relative Strength Index - momentum oscillator measuring speed and magnitude of price changes.",
        formula="1 - (1 / (1 + RS)), where RS = average gain / average loss",
        range=(0.0, 1.0),
        unit="normalized",
        source_module="src.core.features",
        aliases={"RelativeStrengthIndex"},
        examples=["RSI > 0.7 indicates overbought", "RSI < 0.3 indicates oversold"],
    )
    
    glossary.add_term(
        term="MACD",
        category=TermCategory.INDICATOR,
        definition="Moving Average Convergence Divergence - trend-following momentum indicator.",
        formula="EMA(12) - EMA(26)",
        source_module="src.core.features",
        aliases={"MovingAverageConvergenceDivergence"},
        related_terms={"EMA"},
    )
    
    glossary.add_term(
        term="Volatility",
        category=TermCategory.INDICATOR,
        definition="Statistical measure of price dispersion, calculated as annualized standard deviation of returns.",
        formula="σ(returns) × sqrt(periods)",
        source_module="src.core.features",
        related_terms={"RSI"},
    )
    
    glossary.add_term(
        term="EMA",
        category=TermCategory.INDICATOR,
        definition="Exponential Moving Average - weighted average giving more importance to recent prices.",
        source_module="src.core.features",
        aliases={"ExponentialMovingAverage"},
        related_terms={"MACD"},
    )
    
    # Concepts
    glossary.add_term(
        term="MarketSnapshot",
        category=TermCategory.CONCEPT,
        definition="Point-in-time capture of all relevant market data for a token, including price, volume, liquidity, and metadata.",
        source_module="src.core.features",
        related_terms={"FeatureVector"},
    )
    
    glossary.add_term(
        term="FeatureVector",
        category=TermCategory.CONCEPT,
        definition="Normalized collection of all computed features for a token, ready for scoring or ML models.",
        source_module="src.core.features",
        related_terms={"MarketSnapshot", "GemScore"},
    )
    
    glossary.add_term(
        term="HiddenGem",
        category=TermCategory.CONCEPT,
        definition="A token with high growth potential that is currently undervalued or overlooked by the broader market.",
        related_terms={"GemScore"},
    )
    
    # Algorithms
    glossary.add_term(
        term="LiquidityGuardrail",
        category=TermCategory.ALGORITHM,
        definition="Safety check ensuring minimum liquidity threshold before allowing a token into the review queue.",
        source_module="src.core.safety",
        related_terms={"ContractSafety", "LiquidityDepth"},
    )
    
    glossary.add_term(
        term="PenaltyApplication",
        category=TermCategory.ALGORITHM,
        definition="Process of applying multiplicative penalties to features based on risk factors and safety concerns.",
        source_module="src.core.safety",
        related_terms={"ContractSafety", "TokenomicsRisk"},
    )
    
    # Data sources
    glossary.add_term(
        term="Etherscan",
        category=TermCategory.DATA_SOURCE,
        definition="Blockchain explorer for Ethereum providing contract data, transaction history, and token metrics.",
        source_module="src.core.clients",
    )
    
    glossary.add_term(
        term="DEXScreener",
        category=TermCategory.DATA_SOURCE,
        definition="Real-time price and liquidity data aggregator for decentralized exchanges.",
        source_module="src.core.clients",
        aliases={"DexScreener"},
    )
    
    return glossary


# Global glossary instance
_global_glossary = create_default_glossary()


def get_glossary() -> GlossaryBuilder:
    """Get the global glossary instance."""
    return _global_glossary


def reset_glossary() -> None:
    """Reset the global glossary (useful for testing)."""
    global _global_glossary
    _global_glossary = create_default_glossary()
