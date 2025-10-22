"""FastAPI routes for experiment tracking and analysis."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.utils.experiment_tracker import ExperimentConfig, ExperimentRegistry
from backtest.harness import BacktestResult
from backtest.extended_metrics import ExtendedBacktestMetrics

logger = logging.getLogger(__name__)

# Initialize limiter for this router
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/experiments", tags=["Experiments"])

# Initialize global registry
_registry: Optional[ExperimentRegistry] = None


def get_registry() -> ExperimentRegistry:
    """Get or create the experiment registry."""
    global _registry
    if _registry is None:
        _registry = ExperimentRegistry()
    return _registry


# ============================================================================
# Response Models
# ============================================================================

class ExperimentSummary(BaseModel):
    """Summary information for an experiment."""
    config_hash: str = Field(..., description="Experiment configuration hash")
    short_hash: str = Field(..., description="Short hash for display (first 12 chars)")
    created_at: str = Field(..., description="ISO timestamp of creation")
    description: str = Field(default="", description="Experiment description")
    tags: List[str] = Field(default_factory=list, description="Experiment tags")
    feature_count: int = Field(..., description="Number of features used")
    has_results: bool = Field(default=False, description="Whether backtest results exist")


class ExperimentDetailResponse(BaseModel):
    """Detailed experiment information."""
    config: Dict[str, Any] = Field(..., description="Complete experiment configuration")
    config_hash: str = Field(..., description="Configuration hash")
    created_at: str = Field(..., description="Creation timestamp")
    results: Optional[Dict[str, Any]] = Field(None, description="Backtest results if available")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Performance metrics")
    execution_tree: Optional[Dict[str, Any]] = Field(None, description="Execution tree structure")


class ComparisonResponse(BaseModel):
    """Side-by-side experiment comparison."""
    config1_hash: str = Field(..., description="First experiment hash (short)")
    config2_hash: str = Field(..., description="Second experiment hash (short)")
    features: Dict[str, List[str]] = Field(..., description="Feature set differences")
    weight_differences: Dict[str, Dict[str, float]] = Field(..., description="Weight deltas")
    hyperparameters: Dict[str, Dict[str, Any]] = Field(..., description="Hyperparameter comparison")
    metrics_comparison: Optional[Dict[str, Any]] = Field(None, description="Performance metrics comparison")


class ArtifactExportRequest(BaseModel):
    """Request for artifact export."""
    config_hash: str = Field(..., description="Experiment hash to export")
    format: str = Field("json", description="Export format (json or pdf)")
    include_metrics: bool = Field(True, description="Include metrics in export")
    include_config: bool = Field(True, description="Include configuration in export")


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/", response_model=List[ExperimentSummary])
@limiter.limit("60/minute")
def list_experiments(
    request: Request,
    limit: int = Query(100, ge=1, le=500, description="Maximum number of experiments"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search in description"),
) -> List[ExperimentSummary]:
    """List all experiments with optional filtering.
    
    Args:
        limit: Maximum number of experiments to return
        tag: Optional tag filter
        search: Optional search term for descriptions
        
    Returns:
        List of experiment summaries
    """
    registry = get_registry()
    
    # Get experiments based on tag filter
    if tag:
        experiments = registry.search_by_tag(tag)
    else:
        experiments = registry.list_all(limit=limit)
    
    # Apply search filter if provided
    if search:
        search_lower = search.lower()
        experiments = [
            exp for exp in experiments
            if search_lower in exp.description.lower()
        ]
    
    # Convert to summaries
    summaries = []
    for exp in experiments[:limit]:
        # Check if results exist
        results_path = Path(f"backtest_results/{exp.config_hash[:12]}.json")
        has_results = results_path.exists()
        
        summaries.append(ExperimentSummary(
            config_hash=exp.config_hash,
            short_hash=exp.config_hash[:12],
            created_at=exp.created_at or "",
            description=exp.description,
            tags=exp.tags,
            feature_count=len(exp.feature_names),
            has_results=has_results,
        ))
    
    return summaries


@router.get("/{config_hash}", response_model=ExperimentDetailResponse)
@limiter.limit("60/minute")
def get_experiment_detail(
    request: Request,
    config_hash: str,
    include_results: bool = Query(True, description="Include backtest results"),
    include_tree: bool = Query(True, description="Include execution tree"),
) -> ExperimentDetailResponse:
    """Get detailed information for a specific experiment.
    
    Args:
        config_hash: Experiment configuration hash (full or partial)
        include_results: Whether to include backtest results
        include_tree: Whether to include execution tree
        
    Returns:
        Detailed experiment information
    """
    registry = get_registry()
    exp = registry.get(config_hash)
    
    if not exp:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment {config_hash} not found"
        )
    
    response = ExperimentDetailResponse(
        config=exp.to_dict(),
        config_hash=exp.config_hash,
        created_at=exp.created_at or "",
    )
    
    # Load results if requested and available
    if include_results:
        results_path = Path(f"backtest_results/{exp.config_hash[:12]}.json")
        if results_path.exists():
            try:
                with open(results_path, 'r') as f:
                    results_data = json.load(f)
                    response.results = results_data
                    
                    # Extract metrics if available
                    if "extended_metrics" in results_data:
                        response.metrics = results_data["extended_metrics"]
            except Exception as e:
                logger.error(f"Error loading results for {config_hash}: {e}")
    
    # Load execution tree if requested
    if include_tree:
        tree_path = Path(f"execution_trees/{exp.config_hash[:12]}.json")
        if tree_path.exists():
            try:
                with open(tree_path, 'r') as f:
                    response.execution_tree = json.load(f)
            except Exception as e:
                logger.error(f"Error loading execution tree for {config_hash}: {e}")
    
    return response


@router.get("/{config_hash}/metrics")
@limiter.limit("60/minute")
def get_experiment_metrics(
    request: Request,
    config_hash: str,
) -> Dict[str, Any]:
    """Get performance metrics for an experiment.
    
    Args:
        config_hash: Experiment configuration hash
        
    Returns:
        Performance metrics including precision, IC, risk metrics
    """
    registry = get_registry()
    exp = registry.get(config_hash)
    
    if not exp:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment {config_hash} not found"
        )
    
    results_path = Path(f"backtest_results/{exp.config_hash[:12]}.json")
    if not results_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No backtest results found for experiment {config_hash[:12]}"
        )
    
    try:
        with open(results_path, 'r') as f:
            results = json.load(f)
            
        # Return metrics in structured format
        return {
            "config_hash": exp.config_hash[:12],
            "precision_at_k": results.get("precision_at_k", 0.0),
            "average_return_at_k": results.get("average_return_at_k", 0.0),
            "extended_metrics": results.get("extended_metrics", {}),
            "baseline_results": results.get("baseline_results", {}),
            "flagged_assets": results.get("flagged_assets", []),
        }
    except Exception as e:
        logger.error(f"Error loading metrics for {config_hash}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load metrics: {str(e)}"
        )


@router.get("/{config_hash}/tree")
@limiter.limit("60/minute")
def get_execution_tree(
    request: Request,
    config_hash: str,
) -> Dict[str, Any]:
    """Get execution tree for an experiment run.
    
    Args:
        config_hash: Experiment configuration hash
        
    Returns:
        Execution tree structure with nodes, decisions, and outcomes
    """
    registry = get_registry()
    exp = registry.get(config_hash)
    
    if not exp:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment {config_hash} not found"
        )
    
    tree_path = Path(f"execution_trees/{exp.config_hash[:12]}.json")
    if not tree_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No execution tree found for experiment {config_hash[:12]}"
        )
    
    try:
        with open(tree_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading execution tree for {config_hash}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load execution tree: {str(e)}"
        )


@router.get("/compare/{hash1}/{hash2}", response_model=ComparisonResponse)
@limiter.limit("60/minute")
def compare_experiments(
    request: Request,
    hash1: str,
    hash2: str,
    include_metrics: bool = Query(True, description="Include metrics comparison"),
) -> ComparisonResponse:
    """Compare two experiments side-by-side.
    
    Args:
        hash1: First experiment hash
        hash2: Second experiment hash
        include_metrics: Whether to include metrics comparison
        
    Returns:
        Comparison results with feature, weight, and metric deltas
    """
    registry = get_registry()
    
    # Get comparison from registry
    comparison = registry.compare(hash1, hash2)
    
    if "error" in comparison:
        raise HTTPException(
            status_code=404,
            detail=comparison["error"]
        )
    
    response = ComparisonResponse(
        config1_hash=comparison["config1_hash"],
        config2_hash=comparison["config2_hash"],
        features=comparison["features"],
        weight_differences=comparison["weight_differences"],
        hyperparameters=comparison["hyperparameters"],
    )
    
    # Add metrics comparison if requested
    if include_metrics:
        metrics1_path = Path(f"backtest_results/{comparison['config1_hash']}.json")
        metrics2_path = Path(f"backtest_results/{comparison['config2_hash']}.json")
        
        if metrics1_path.exists() and metrics2_path.exists():
            try:
                with open(metrics1_path, 'r') as f1, open(metrics2_path, 'r') as f2:
                    results1 = json.load(f1)
                    results2 = json.load(f2)
                    
                    response.metrics_comparison = {
                        "config1": {
                            "precision_at_k": results1.get("precision_at_k", 0.0),
                            "average_return_at_k": results1.get("average_return_at_k", 0.0),
                            "extended_metrics": results1.get("extended_metrics", {}),
                        },
                        "config2": {
                            "precision_at_k": results2.get("precision_at_k", 0.0),
                            "average_return_at_k": results2.get("average_return_at_k", 0.0),
                            "extended_metrics": results2.get("extended_metrics", {}),
                        },
                        "deltas": {
                            "precision_delta": results2.get("precision_at_k", 0.0) - results1.get("precision_at_k", 0.0),
                            "return_delta": results2.get("average_return_at_k", 0.0) - results1.get("average_return_at_k", 0.0),
                        }
                    }
            except Exception as e:
                logger.error(f"Error loading metrics for comparison: {e}")
    
    return response


@router.post("/export")
@limiter.limit("30/minute")
def export_artifact(
    request: Request,
    export_request: ArtifactExportRequest,
) -> Dict[str, Any]:
    """Export experiment artifact as JSON or PDF.
    
    Args:
        export_request: Export configuration
        
    Returns:
        Export result with file path or content
    """
    registry = get_registry()
    exp = registry.get(export_request.config_hash)
    
    if not exp:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment {export_request.config_hash} not found"
        )
    
    # Build artifact data
    artifact_data = {}
    
    if export_request.include_config:
        artifact_data["config"] = exp.to_dict()
    
    if export_request.include_metrics:
        results_path = Path(f"backtest_results/{exp.config_hash[:12]}.json")
        if results_path.exists():
            with open(results_path, 'r') as f:
                artifact_data["results"] = json.load(f)
    
    # Generate export based on format
    export_dir = Path("exports")
    export_dir.mkdir(exist_ok=True)
    
    if export_request.format == "json":
        export_path = export_dir / f"experiment_{exp.config_hash[:12]}.json"
        with open(export_path, 'w') as f:
            json.dump(artifact_data, f, indent=2, sort_keys=True)
        
        return {
            "status": "success",
            "format": "json",
            "file_path": str(export_path),
            "config_hash": exp.config_hash[:12],
        }
    
    elif export_request.format == "pdf":
        # For PDF export, we'd use a library like reportlab or weasyprint
        # For now, return JSON with a note
        return {
            "status": "not_implemented",
            "message": "PDF export will be implemented with reportlab",
            "format": "pdf",
            "config_hash": exp.config_hash[:12],
        }
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export format: {export_request.format}"
        )


@router.get("/tags/all")
@limiter.limit("60/minute")
def list_all_tags(request: Request) -> Dict[str, List[str]]:
    """Get all unique tags across all experiments.
    
    Returns:
        Dictionary with list of all tags and their frequencies
    """
    registry = get_registry()
    experiments = registry.list_all(limit=1000)
    
    # Count tag frequencies
    tag_counts: Dict[str, int] = {}
    for exp in experiments:
        for tag in exp.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    # Sort by frequency
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "tags": [tag for tag, _ in sorted_tags],
        "tag_counts": dict(sorted_tags),
        "total_experiments": len(experiments),
    }


@router.delete("/{config_hash}")
@limiter.limit("30/minute")
def delete_experiment(
    request: Request,
    config_hash: str,
) -> Dict[str, str]:
    """Delete an experiment from the registry.
    
    Args:
        config_hash: Experiment configuration hash
        
    Returns:
        Deletion status
    """
    registry = get_registry()
    
    # Check if experiment exists
    exp = registry.get(config_hash)
    if not exp:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment {config_hash} not found"
        )
    
    # Delete from registry
    deleted = registry.delete(exp.config_hash)
    
    if not deleted:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete experiment"
        )
    
    return {
        "status": "deleted",
        "config_hash": exp.config_hash[:12],
        "message": f"Experiment {exp.config_hash[:12]} deleted successfully"
    }
