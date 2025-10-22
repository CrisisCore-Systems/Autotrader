"""API endpoints for data drift and freshness monitoring."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.core.logging_config import get_logger
from src.monitoring import (
    IntegratedMonitor,
    FeatureCriticality,
    DriftSeverity,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

# Global monitor instance (in production, this would be dependency-injected)
_monitor: Optional[IntegratedMonitor] = None


def get_monitor() -> IntegratedMonitor:
    """Get or create the global monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = IntegratedMonitor(name="api_monitor")
    return _monitor


# ============================================================================
# Response Models
# ============================================================================

class FeatureHealthResponse(BaseModel):
    """Feature health status response."""
    feature_name: str
    drift_detected: bool
    drift_severity: str
    freshness_level: str
    data_age_seconds: float
    sla_violated: bool
    last_updated: str


class DriftStatisticsResponse(BaseModel):
    """Drift statistics response."""
    test_name: str
    statistic: float
    p_value: float
    threshold: float
    is_drifted: bool
    severity: str
    description: str


class DriftReportResponse(BaseModel):
    """Drift report response."""
    timestamp: str
    metric_type: str
    metric_name: str
    drift_detected: bool
    severity: str
    statistics: List[DriftStatisticsResponse]
    baseline_stats: Dict[str, float]
    current_stats: Dict[str, float]
    recommendations: List[str]


class MonitoringSummaryResponse(BaseModel):
    """Monitoring summary response."""
    timestamp: str
    status: str
    features_monitored: int
    features_drifted: int
    features_stale: int
    sla_violations: int
    critical_features: int
    recommendations: List[str]


class MonitoringDetailResponse(BaseModel):
    """Detailed monitoring report response."""
    timestamp: str
    features_monitored: int
    features_drifted: int
    features_stale: int
    sla_violations: int
    feature_health: Dict[str, FeatureHealthResponse]
    drift_reports: List[DriftReportResponse]
    recommendations: List[str]


class FeatureSLARequest(BaseModel):
    """Request to register feature SLA."""
    feature_name: str = Field(..., description="Feature name")
    max_age_seconds: float = Field(..., gt=0, description="Maximum age in seconds")
    criticality: str = Field(
        default="standard",
        description="Criticality level (critical, important, standard)",
    )
    alert_threshold_seconds: Optional[float] = Field(
        None,
        description="Optional alert threshold (defaults to 80% of max_age)",
    )


class FeatureSLAResponse(BaseModel):
    """Feature SLA registration response."""
    feature_name: str
    max_age_seconds: float
    criticality: str
    alert_threshold_seconds: float
    registered: bool


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/summary", response_model=MonitoringSummaryResponse)
async def get_monitoring_summary() -> MonitoringSummaryResponse:
    """Get monitoring summary.
    
    Returns current monitoring status including drift detection
    and freshness metrics for all monitored features.
    """
    try:
        monitor = get_monitor()
        summary = monitor.get_summary()
        
        if not summary.get("latest_report"):
            return MonitoringSummaryResponse(
                timestamp=datetime.utcnow().isoformat(),
                status="no_data",
                features_monitored=0,
                features_drifted=0,
                features_stale=0,
                sla_violations=0,
                critical_features=len(monitor.critical_features),
                recommendations=["No monitoring data available yet"],
            )
        
        latest = summary["latest_report"]
        
        return MonitoringSummaryResponse(
            timestamp=latest["timestamp"],
            status=summary["current_status"],
            features_monitored=latest["features_monitored"],
            features_drifted=latest["features_drifted"],
            features_stale=latest["features_stale"],
            sla_violations=latest["sla_violations"],
            critical_features=len(monitor.critical_features),
            recommendations=latest["recommendations"],
        )
        
    except Exception as e:
        logger.error("failed_to_get_monitoring_summary", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/details", response_model=MonitoringDetailResponse)
async def get_monitoring_details() -> MonitoringDetailResponse:
    """Get detailed monitoring report.
    
    Returns detailed monitoring information including per-feature
    health status, drift reports, and recommendations.
    """
    try:
        monitor = get_monitor()
        
        if not monitor.reports:
            raise HTTPException(
                status_code=404,
                detail="No monitoring reports available",
            )
        
        latest_report = monitor.reports[-1]
        report_dict = latest_report.to_dict()
        
        # Convert feature health
        feature_health = {
            name: FeatureHealthResponse(**health_dict)
            for name, health_dict in report_dict["feature_health"].items()
        }
        
        # Convert drift reports
        drift_reports = []
        for drift_report in report_dict["drift_reports"]:
            statistics = [
                DriftStatisticsResponse(**stat)
                for stat in drift_report["statistics"]
            ]
            
            drift_reports.append(
                DriftReportResponse(
                    timestamp=drift_report["timestamp"],
                    metric_type=drift_report["metric_type"],
                    metric_name=drift_report["metric_name"],
                    drift_detected=drift_report["drift_detected"],
                    severity=drift_report["severity"],
                    statistics=statistics,
                    baseline_stats=drift_report["baseline_stats"],
                    current_stats=drift_report["current_stats"],
                    recommendations=drift_report["recommendations"],
                )
            )
        
        return MonitoringDetailResponse(
            timestamp=report_dict["timestamp"],
            features_monitored=report_dict["features_monitored"],
            features_drifted=report_dict["features_drifted"],
            features_stale=report_dict["features_stale"],
            sla_violations=report_dict["sla_violations"],
            feature_health=feature_health,
            drift_reports=drift_reports,
            recommendations=report_dict["recommendations"],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_get_monitoring_details", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features", response_model=List[str])
async def get_monitored_features() -> List[str]:
    """Get list of monitored features.
    
    Returns list of feature names currently being monitored.
    """
    try:
        monitor = get_monitor()
        
        if not monitor.drift_monitor.baseline:
            return []
        
        return list(monitor.drift_monitor.baseline.feature_distributions.keys())
        
    except Exception as e:
        logger.error("failed_to_get_monitored_features", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features/{feature_name}", response_model=FeatureHealthResponse)
async def get_feature_health(feature_name: str) -> FeatureHealthResponse:
    """Get health status for specific feature.
    
    Args:
        feature_name: Name of the feature
        
    Returns:
        Feature health status
    """
    try:
        monitor = get_monitor()
        
        if not monitor.reports:
            raise HTTPException(
                status_code=404,
                detail="No monitoring reports available",
            )
        
        latest_report = monitor.reports[-1]
        
        if feature_name not in latest_report.feature_health:
            raise HTTPException(
                status_code=404,
                detail=f"Feature '{feature_name}' not found in monitoring reports",
            )
        
        health = latest_report.feature_health[feature_name]
        
        return FeatureHealthResponse(
            feature_name=health.feature_name,
            drift_detected=health.drift_detected,
            drift_severity=health.drift_severity.value,
            freshness_level=health.freshness_level.value,
            data_age_seconds=health.data_age_seconds,
            sla_violated=health.sla_violated,
            last_updated=health.last_updated.isoformat(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "failed_to_get_feature_health",
            feature=feature_name,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sla/register", response_model=FeatureSLAResponse)
async def register_feature_sla(request: FeatureSLARequest) -> FeatureSLAResponse:
    """Register SLA for a feature.
    
    Registers freshness SLA requirements for a specific feature.
    Critical features will trigger alerts when SLA is violated.
    
    Args:
        request: SLA registration request
        
    Returns:
        SLA registration confirmation
    """
    try:
        monitor = get_monitor()
        
        # Parse criticality
        try:
            criticality = FeatureCriticality(request.criticality.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid criticality: {request.criticality}. "
                       "Must be one of: critical, important, standard",
            )
        
        # Register SLA
        monitor.register_feature_sla(
            feature_name=request.feature_name,
            max_age_seconds=request.max_age_seconds,
            criticality=criticality,
            alert_threshold_seconds=request.alert_threshold_seconds,
        )
        
        # Get the registered SLA
        sla = monitor.feature_slas[request.feature_name]
        
        return FeatureSLAResponse(
            feature_name=request.feature_name,
            max_age_seconds=sla.max_age_seconds,
            criticality=sla.criticality.value,
            alert_threshold_seconds=sla.alert_threshold_seconds,
            registered=True,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "failed_to_register_feature_sla",
            feature=request.feature_name,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sla/list", response_model=Dict[str, FeatureSLAResponse])
async def list_feature_slas() -> Dict[str, FeatureSLAResponse]:
    """List all registered feature SLAs.
    
    Returns dictionary of feature name to SLA configuration.
    """
    try:
        monitor = get_monitor()
        
        return {
            name: FeatureSLAResponse(
                feature_name=name,
                max_age_seconds=sla.max_age_seconds,
                criticality=sla.criticality.value,
                alert_threshold_seconds=sla.alert_threshold_seconds,
                registered=True,
            )
            for name, sla in monitor.feature_slas.items()
        }
        
    except Exception as e:
        logger.error("failed_to_list_feature_slas", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[MonitoringSummaryResponse])
async def get_monitoring_history(
    limit: int = Query(10, ge=1, le=100, description="Number of reports to return"),
) -> List[MonitoringSummaryResponse]:
    """Get monitoring history.
    
    Args:
        limit: Maximum number of historical reports to return
        
    Returns:
        List of monitoring summaries
    """
    try:
        monitor = get_monitor()
        
        if not monitor.reports:
            return []
        
        # Get last N reports
        reports = monitor.reports[-limit:]
        
        results = []
        for report in reports:
            status = monitor._determine_overall_status(report)
            
            results.append(
                MonitoringSummaryResponse(
                    timestamp=report.timestamp.isoformat(),
                    status=status,
                    features_monitored=report.features_monitored,
                    features_drifted=report.features_drifted,
                    features_stale=report.features_stale,
                    sla_violations=report.sla_violations,
                    critical_features=len(monitor.critical_features),
                    recommendations=report.recommendations,
                )
            )
        
        return results
        
    except Exception as e:
        logger.error("failed_to_get_monitoring_history", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
