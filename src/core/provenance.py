"""Artifact provenance tracking for the Hidden-Gem Scanner.

This module provides comprehensive lineage tracking for data artifacts,
transformations, and dependencies throughout the analysis pipeline.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4


class ArtifactType(Enum):
    """Types of artifacts tracked in the system."""
    
    RAW_DATA = "raw_data"
    MARKET_SNAPSHOT = "market_snapshot"
    PRICE_SERIES = "price_series"
    FEATURE_VECTOR = "feature_vector"
    GEM_SCORE = "gem_score"
    CONTRACT_REPORT = "contract_report"
    NARRATIVE_EMBEDDING = "narrative_embedding"
    AGGREGATED_METRICS = "aggregated_metrics"
    REPORT = "report"


class TransformationType(Enum):
    """Types of transformations applied to artifacts."""
    
    INGESTION = "ingestion"
    FEATURE_EXTRACTION = "feature_extraction"
    NORMALIZATION = "normalization"
    AGGREGATION = "aggregation"
    SCORING = "scoring"
    PENALTY_APPLICATION = "penalty_application"
    FILTERING = "filtering"
    ENRICHMENT = "enrichment"


@dataclass
class ArtifactMetadata:
    """Metadata describing an artifact's properties and origin."""
    
    artifact_id: str = field(default_factory=lambda: str(uuid4()))
    artifact_type: ArtifactType = ArtifactType.RAW_DATA
    name: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
    schema_version: str = "1.0"
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        d = asdict(self)
        d["artifact_type"] = self.artifact_type.value
        d["created_at"] = self.created_at.isoformat()
        d["tags"] = list(self.tags)
        return d


@dataclass
class Transformation:
    """Represents a transformation applied to create an artifact."""
    
    transformation_id: str = field(default_factory=lambda: str(uuid4()))
    transformation_type: TransformationType = TransformationType.INGESTION
    applied_at: datetime = field(default_factory=datetime.utcnow)
    function_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    status: str = "success"
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        d = asdict(self)
        d["transformation_type"] = self.transformation_type.value
        d["applied_at"] = self.applied_at.isoformat()
        return d


@dataclass
class ProvenanceRecord:
    """Complete provenance record for an artifact including lineage."""
    
    artifact: ArtifactMetadata
    parent_artifacts: List[str] = field(default_factory=list)
    transformations: List[Transformation] = field(default_factory=list)
    child_artifacts: List[str] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    annotations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "artifact": self.artifact.to_dict(),
            "parent_artifacts": self.parent_artifacts,
            "transformations": [t.to_dict() for t in self.transformations],
            "child_artifacts": self.child_artifacts,
            "data_sources": self.data_sources,
            "quality_metrics": self.quality_metrics,
            "annotations": self.annotations,
        }
    
    def compute_checksum(self, data: Any) -> str:
        """Compute SHA256 checksum of artifact data."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()


class ProvenanceTracker:
    """Central registry for tracking artifact provenance."""
    
    def __init__(self):
        """Initialize the provenance tracker."""
        self.records: Dict[str, ProvenanceRecord] = {}
        self.lineage_graph: Dict[str, Set[str]] = {}  # artifact_id -> set of parent_ids
        
    def register_artifact(
        self,
        artifact_type: ArtifactType,
        name: str,
        data: Any,
        parent_ids: Optional[List[str]] = None,
        transformation: Optional[Transformation] = None,
        data_source: Optional[str] = None,
        tags: Optional[Set[str]] = None,
        custom_attributes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a new artifact with provenance tracking.
        
        Parameters
        ----------
        artifact_type : ArtifactType
            The type of artifact being registered.
        name : str
            Human-readable name for the artifact.
        data : Any
            The actual artifact data (used for checksum).
        parent_ids : Optional[List[str]]
            IDs of parent artifacts this was derived from.
        transformation : Optional[Transformation]
            Transformation applied to create this artifact.
        data_source : Optional[str]
            External data source if applicable.
        tags : Optional[Set[str]]
            Tags for categorization.
        custom_attributes : Optional[Dict[str, Any]]
            Additional custom metadata.
            
        Returns
        -------
        str
            The unique artifact ID.
        """
        metadata = ArtifactMetadata(
            artifact_type=artifact_type,
            name=name,
            tags=tags or set(),
            custom_attributes=custom_attributes or {},
        )
        
        record = ProvenanceRecord(artifact=metadata)
        
        # Compute checksum
        try:
            record.artifact.checksum = record.compute_checksum(data)
        except Exception:
            record.artifact.checksum = None
        
        # Track lineage
        if parent_ids:
            record.parent_artifacts = parent_ids
            self.lineage_graph[metadata.artifact_id] = set(parent_ids)
            
            # Update parent records with child reference
            for parent_id in parent_ids:
                if parent_id in self.records:
                    self.records[parent_id].child_artifacts.append(metadata.artifact_id)
        
        if transformation:
            record.transformations.append(transformation)
        
        if data_source:
            record.data_sources.append(data_source)
        
        self.records[metadata.artifact_id] = record
        return metadata.artifact_id
    
    def add_transformation(
        self,
        artifact_id: str,
        transformation: Transformation,
    ) -> None:
        """Add a transformation to an existing artifact's provenance."""
        if artifact_id in self.records:
            self.records[artifact_id].transformations.append(transformation)
    
    def add_quality_metrics(
        self,
        artifact_id: str,
        metrics: Dict[str, float],
    ) -> None:
        """Add quality metrics to an artifact's provenance."""
        if artifact_id in self.records:
            self.records[artifact_id].quality_metrics.update(metrics)
    
    def add_annotation(
        self,
        artifact_id: str,
        annotation: str,
    ) -> None:
        """Add a human-readable annotation to an artifact."""
        if artifact_id in self.records:
            self.records[artifact_id].annotations.append(annotation)
    
    def get_record(self, artifact_id: str) -> Optional[ProvenanceRecord]:
        """Retrieve provenance record for an artifact."""
        return self.records.get(artifact_id)
    
    def get_lineage(self, artifact_id: str, depth: int = -1) -> List[str]:
        """Get complete lineage (ancestors) of an artifact.
        
        Parameters
        ----------
        artifact_id : str
            The artifact to trace lineage for.
        depth : int
            Maximum depth to traverse (-1 for unlimited).
            
        Returns
        -------
        List[str]
            List of ancestor artifact IDs in topological order.
        """
        visited = set()
        lineage = []
        
        def traverse(aid: str, current_depth: int):
            if depth != -1 and current_depth > depth:
                return
            if aid in visited:
                return
            visited.add(aid)
            
            if aid in self.lineage_graph:
                for parent_id in self.lineage_graph[aid]:
                    traverse(parent_id, current_depth + 1)
            
            lineage.append(aid)
        
        traverse(artifact_id, 0)
        return lineage
    
    def get_descendants(self, artifact_id: str) -> List[str]:
        """Get all descendant artifacts."""
        if artifact_id not in self.records:
            return []
        
        descendants = []
        visited = set()
        
        def traverse(aid: str):
            if aid in visited:
                return
            visited.add(aid)
            
            record = self.records.get(aid)
            if record:
                for child_id in record.child_artifacts:
                    descendants.append(child_id)
                    traverse(child_id)
        
        traverse(artifact_id)
        return descendants
    
    def export_lineage_graph(self, artifact_id: str, format: str = "dict") -> Any:
        """Export lineage graph in various formats.
        
        Parameters
        ----------
        artifact_id : str
            Root artifact to export from.
        format : str
            Output format: 'dict', 'json', 'mermaid'.
            
        Returns
        -------
        Any
            Lineage graph in requested format.
        """
        lineage_ids = self.get_lineage(artifact_id)
        
        if format == "mermaid":
            return self._export_mermaid(lineage_ids)
        elif format == "json":
            graph = self._build_graph_dict(lineage_ids)
            return json.dumps(graph, indent=2)
        else:  # dict
            return self._build_graph_dict(lineage_ids)
    
    def _build_graph_dict(self, artifact_ids: List[str]) -> Dict[str, Any]:
        """Build a dictionary representation of the lineage graph."""
        nodes = []
        edges = []
        
        for aid in artifact_ids:
            record = self.records.get(aid)
            if record:
                nodes.append({
                    "id": aid,
                    "type": record.artifact.artifact_type.value,
                    "name": record.artifact.name,
                    "created_at": record.artifact.created_at.isoformat(),
                })
                
                for parent_id in record.parent_artifacts:
                    edges.append({
                        "source": parent_id,
                        "target": aid,
                    })
        
        return {"nodes": nodes, "edges": edges}
    
    def _export_mermaid(self, artifact_ids: List[str]) -> str:
        """Export lineage as Mermaid diagram syntax."""
        lines = ["graph TD"]
        
        for aid in artifact_ids:
            record = self.records.get(aid)
            if record:
                short_id = aid[:8]
                node_label = f"{record.artifact.name}<br/>{record.artifact.artifact_type.value}"
                lines.append(f'    {short_id}["{node_label}"]')
                
                for parent_id in record.parent_artifacts:
                    parent_short = parent_id[:8]
                    lines.append(f"    {parent_short} --> {short_id}")
        
        return "\n".join(lines)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about tracked artifacts."""
        type_counts = {}
        total_transformations = 0
        
        for record in self.records.values():
            artifact_type = record.artifact.artifact_type.value
            type_counts[artifact_type] = type_counts.get(artifact_type, 0) + 1
            total_transformations += len(record.transformations)
        
        return {
            "total_artifacts": len(self.records),
            "artifacts_by_type": type_counts,
            "total_transformations": total_transformations,
            "lineage_edges": sum(len(parents) for parents in self.lineage_graph.values()),
        }


# Global provenance tracker instance
_global_tracker = ProvenanceTracker()


def get_provenance_tracker() -> ProvenanceTracker:
    """Get the global provenance tracker instance."""
    return _global_tracker


def reset_provenance_tracker() -> None:
    """Reset the global provenance tracker (useful for testing)."""
    global _global_tracker
    _global_tracker = ProvenanceTracker()
