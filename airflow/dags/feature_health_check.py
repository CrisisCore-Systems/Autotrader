"""
Feature Health Check DAG for AutoTrader
Hourly drift detection, feature quality monitoring, and alerting.

Schedule: Hourly
SLA: 15 minutes
"""

from datetime import timedelta
from typing import Dict, Any, List
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

# Configure logging
logger = logging.getLogger(__name__)

# Default arguments
default_args = {
    'owner': 'autotrader',
    'depends_on_past': False,
    'email': ['alerts@autotrader.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
    'sla': timedelta(minutes=15),
}


def detect_feature_drift(**context) -> Dict[str, Any]:
    """
    Detect feature drift using statistical tests.
    
    Methods:
    - Population Stability Index (PSI)
    - Kolmogorov-Smirnov test
    - Jensen-Shannon divergence
    
    Returns:
        Dict with drift detection results
    """
    from autotrader.monitoring.drift_detector import DriftDetector
    from autotrader.features.feature_store import FeatureStore
    
    execution_date = context['execution_date']
    logger.info(f"Detecting feature drift at {execution_date}")
    
    drift_results = {
        'execution_date': execution_date.isoformat(),
        'total_features': 0,
        'drifted_features': [],
        'critical_drift': [],
        'warning_drift': [],
        'stable_features': 0,
        'alerts': []
    }
    
    try:
        # Load current and reference features
        feature_store = FeatureStore()
        current_features = feature_store.get_latest_features()
        reference_features = feature_store.get_reference_features()
        
        drift_results['total_features'] = len(current_features.columns)
        
        # Initialize drift detector
        drift_detector = DriftDetector()
        
        # Detect drift for each feature
        for feature_name in current_features.columns:
            current_dist = current_features[feature_name].dropna()
            reference_dist = reference_features[feature_name].dropna()
            
            # Calculate PSI
            psi = drift_detector.calculate_psi(
                reference=reference_dist,
                current=current_dist
            )
            
            # Calculate KS statistic
            ks_stat, ks_pvalue = drift_detector.ks_test(
                reference=reference_dist,
                current=current_dist
            )
            
            # Calculate JS divergence
            js_div = drift_detector.js_divergence(
                reference=reference_dist,
                current=current_dist
            )
            
            drift_info = {
                'feature': feature_name,
                'psi': psi,
                'ks_statistic': ks_stat,
                'ks_pvalue': ks_pvalue,
                'js_divergence': js_div
            }
            
            # Classify drift level
            if psi > 0.3:  # Critical drift
                drift_results['critical_drift'].append(drift_info)
                drift_results['drifted_features'].append(feature_name)
                drift_results['alerts'].append(
                    f"🔴 CRITICAL: {feature_name} PSI={psi:.3f}"
                )
                logger.critical(f"Critical drift: {feature_name} PSI={psi:.3f}")
            
            elif psi > 0.2:  # Warning drift
                drift_results['warning_drift'].append(drift_info)
                drift_results['drifted_features'].append(feature_name)
                logger.warning(f"Warning drift: {feature_name} PSI={psi:.3f}")
            
            else:  # Stable
                drift_results['stable_features'] += 1
        
        logger.info(
            f"Drift detection complete: "
            f"{len(drift_results['critical_drift'])} critical, "
            f"{len(drift_results['warning_drift'])} warning, "
            f"{drift_results['stable_features']} stable"
        )
        
        # Send alerts for critical drift
        if drift_results['critical_drift']:
            _send_drift_alert(drift_results['critical_drift'])
    
    except Exception as e:
        logger.error(f"Drift detection error: {e}")
        drift_results['alerts'].append(f"ERROR: {str(e)}")
        raise
    
    return drift_results


def _send_drift_alert(critical_drifts: List[Dict[str, Any]]):
    """Send alert for critical feature drift."""
    message = "🚨 Critical Feature Drift Detected!\n\n"
    for drift in critical_drifts:
        message += (
            f"Feature: {drift['feature']}\n"
            f"PSI: {drift['psi']:.3f}\n"
            f"KS Stat: {drift['ks_statistic']:.3f}\n\n"
        )
    logger.critical(message)
    # Would send PagerDuty/Slack alert here


def check_feature_quality(**context) -> Dict[str, Any]:
    """
    Check feature quality metrics.
    
    Checks:
    - Missing value rate
    - Value range validation
    - Correlation stability
    - Outlier detection
    
    Returns:
        Dict with quality check results
    """
    from autotrader.features.feature_store import FeatureStore
    from autotrader.monitoring.quality_checker import QualityChecker
    
    execution_date = context['execution_date']
    logger.info(f"Checking feature quality at {execution_date}")
    
    quality_results = {
        'execution_date': execution_date.isoformat(),
        'total_features': 0,
        'quality_issues': [],
        'missing_rate_violations': [],
        'range_violations': [],
        'correlation_changes': [],
        'outliers_detected': [],
        'alerts': []
    }
    
    try:
        # Load features
        feature_store = FeatureStore()
        features = feature_store.get_latest_features()
        feature_metadata = feature_store.get_feature_metadata()
        
        quality_results['total_features'] = len(features.columns)
        
        # Initialize quality checker
        quality_checker = QualityChecker()
        
        # Check missing values
        for feature_name in features.columns:
            missing_rate = features[feature_name].isna().mean()
            
            if missing_rate > 0.10:  # Critical: >10% missing
                quality_results['missing_rate_violations'].append({
                    'feature': feature_name,
                    'missing_rate': missing_rate,
                    'severity': 'critical'
                })
                quality_results['alerts'].append(
                    f"🔴 {feature_name}: {missing_rate:.1%} missing values"
                )
                logger.critical(f"High missing rate: {feature_name} {missing_rate:.1%}")
            
            elif missing_rate > 0.05:  # Warning: >5% missing
                quality_results['missing_rate_violations'].append({
                    'feature': feature_name,
                    'missing_rate': missing_rate,
                    'severity': 'warning'
                })
                logger.warning(f"Elevated missing rate: {feature_name} {missing_rate:.1%}")
        
        # Check value ranges
        for feature_name, metadata in feature_metadata.items():
            if feature_name not in features.columns:
                continue
            
            feature_data = features[feature_name].dropna()
            expected_min = metadata.get('expected_min')
            expected_max = metadata.get('expected_max')
            
            if expected_min is not None and feature_data.min() < expected_min:
                quality_results['range_violations'].append({
                    'feature': feature_name,
                    'actual_min': float(feature_data.min()),
                    'expected_min': expected_min,
                    'type': 'below_min'
                })
                logger.warning(
                    f"Range violation: {feature_name} "
                    f"min={feature_data.min():.3f} < {expected_min:.3f}"
                )
            
            if expected_max is not None and feature_data.max() > expected_max:
                quality_results['range_violations'].append({
                    'feature': feature_name,
                    'actual_max': float(feature_data.max()),
                    'expected_max': expected_max,
                    'type': 'above_max'
                })
                logger.warning(
                    f"Range violation: {feature_name} "
                    f"max={feature_data.max():.3f} > {expected_max:.3f}"
                )
        
        # Check correlation stability
        current_corr = features.corr()
        reference_corr = feature_store.get_reference_correlation()
        
        corr_changes = quality_checker.detect_correlation_changes(
            current_corr, reference_corr, threshold=0.3
        )
        
        for change in corr_changes:
            quality_results['correlation_changes'].append(change)
            if abs(change['change']) > 0.5:  # Large correlation change
                quality_results['alerts'].append(
                    f"⚠️ Correlation change: {change['feature1']} <-> "
                    f"{change['feature2']}: {change['change']:+.2f}"
                )
        
        # Detect outliers
        outliers = quality_checker.detect_outliers(features, method='iqr')
        quality_results['outliers_detected'] = outliers
        
        logger.info(
            f"Quality check complete: "
            f"{len(quality_results['missing_rate_violations'])} missing violations, "
            f"{len(quality_results['range_violations'])} range violations, "
            f"{len(quality_results['correlation_changes'])} correlation changes"
        )
        
        # Send alerts if critical issues
        if quality_results['alerts']:
            _send_quality_alert(quality_results)
    
    except Exception as e:
        logger.error(f"Quality check error: {e}")
        quality_results['alerts'].append(f"ERROR: {str(e)}")
        raise
    
    return quality_results


def _send_quality_alert(quality_results: Dict[str, Any]):
    """Send alert for quality issues."""
    if not quality_results['alerts']:
        return
    
    message = "⚠️ Feature Quality Issues Detected!\n\n"
    for alert in quality_results['alerts']:
        message += f"{alert}\n"
    
    logger.warning(message)
    # Would send Slack alert here


def monitor_model_performance(**context) -> Dict[str, Any]:
    """
    Monitor model prediction performance.
    
    Tracks:
    - Prediction accuracy
    - Confidence distribution
    - Feature importance changes
    - Prediction power decay
    
    Returns:
        Dict with performance monitoring results
    """
    from autotrader.models.model_registry import ModelRegistry
    from autotrader.monitoring.performance_monitor import PerformanceMonitor
    from autotrader.features.feature_store import FeatureStore
    
    execution_date = context['execution_date']
    logger.info(f"Monitoring model performance at {execution_date}")
    
    perf_results = {
        'execution_date': execution_date.isoformat(),
        'model_version': None,
        'accuracy_metrics': {},
        'confidence_stats': {},
        'feature_importance_changes': [],
        'performance_degradation': False,
        'alerts': []
    }
    
    try:
        # Load current production model
        registry = ModelRegistry()
        model = registry.get_production_model()
        perf_results['model_version'] = model.version
        
        # Load recent predictions and actuals
        feature_store = FeatureStore()
        recent_data = feature_store.get_recent_labeled_data(hours=24)
        
        if len(recent_data) < 100:  # Need minimum data
            logger.warning("Insufficient data for performance monitoring")
            return perf_results
        
        # Initialize performance monitor
        perf_monitor = PerformanceMonitor(model)
        
        # Calculate accuracy metrics
        predictions = model.predict(recent_data.drop('target', axis=1))
        actuals = recent_data['target']
        
        accuracy_metrics = perf_monitor.calculate_accuracy(predictions, actuals)
        perf_results['accuracy_metrics'] = accuracy_metrics
        
        # Analyze confidence distribution
        if hasattr(model, 'predict_proba'):
            probas = model.predict_proba(recent_data.drop('target', axis=1))
            confidence_stats = perf_monitor.analyze_confidence(probas)
            perf_results['confidence_stats'] = confidence_stats
            
            # Check for low confidence
            if confidence_stats['mean_confidence'] < 0.6:
                perf_results['alerts'].append(
                    f"⚠️ Low model confidence: {confidence_stats['mean_confidence']:.2%}"
                )
                logger.warning(
                    f"Low confidence: {confidence_stats['mean_confidence']:.2%}"
                )
        
        # Check feature importance changes
        if hasattr(model, 'feature_importances_'):
            current_importance = dict(zip(
                recent_data.drop('target', axis=1).columns,
                model.feature_importances_
            ))
            
            reference_importance = registry.get_reference_importance(model.version)
            
            importance_changes = perf_monitor.detect_importance_changes(
                current_importance, reference_importance, threshold=0.3
            )
            
            perf_results['feature_importance_changes'] = importance_changes
            
            if importance_changes:
                logger.info(f"Feature importance changes: {len(importance_changes)}")
        
        # Check for performance degradation
        baseline_accuracy = registry.get_baseline_accuracy(model.version)
        current_accuracy = accuracy_metrics.get('accuracy', 0)
        
        if current_accuracy < baseline_accuracy * 0.9:  # >10% degradation
            perf_results['performance_degradation'] = True
            perf_results['alerts'].append(
                f"🔴 Performance degradation: "
                f"{current_accuracy:.2%} vs baseline {baseline_accuracy:.2%}"
            )
            logger.critical(
                f"Performance degradation detected: "
                f"{current_accuracy:.2%} < {baseline_accuracy:.2%}"
            )
        
        logger.info(
            f"Performance monitoring complete: "
            f"accuracy={current_accuracy:.2%}, "
            f"baseline={baseline_accuracy:.2%}"
        )
        
        # Send alerts if degradation
        if perf_results['performance_degradation']:
            _send_performance_alert(perf_results)
    
    except Exception as e:
        logger.error(f"Performance monitoring error: {e}")
        perf_results['alerts'].append(f"ERROR: {str(e)}")
        raise
    
    return perf_results


def _send_performance_alert(perf_results: Dict[str, Any]):
    """Send alert for performance degradation."""
    message = (
        f"🚨 Model Performance Degradation!\n\n"
        f"Model: {perf_results['model_version']}\n"
        f"Current Accuracy: {perf_results['accuracy_metrics'].get('accuracy', 0):.2%}\n"
    )
    
    logger.critical(message)
    # Would send PagerDuty alert here


def generate_health_report(**context) -> Dict[str, Any]:
    """
    Generate comprehensive health report.
    
    Aggregates results from all health checks.
    
    Returns:
        Dict with health report
    """
    ti = context['ti']
    execution_date = context['execution_date']
    
    # Pull results from previous tasks
    drift_results = ti.xcom_pull(task_ids='detect_feature_drift')
    quality_results = ti.xcom_pull(task_ids='check_feature_quality')
    perf_results = ti.xcom_pull(task_ids='monitor_model_performance')
    
    logger.info("Generating health report")
    
    health_report = {
        'execution_date': execution_date.isoformat(),
        'overall_health': 'healthy',
        'drift_summary': {
            'critical': len(drift_results.get('critical_drift', [])),
            'warning': len(drift_results.get('warning_drift', [])),
            'stable': drift_results.get('stable_features', 0)
        },
        'quality_summary': {
            'missing_violations': len(quality_results.get('missing_rate_violations', [])),
            'range_violations': len(quality_results.get('range_violations', [])),
            'correlation_changes': len(quality_results.get('correlation_changes', []))
        },
        'performance_summary': {
            'model_version': perf_results.get('model_version'),
            'degradation': perf_results.get('performance_degradation', False),
            'accuracy': perf_results.get('accuracy_metrics', {}).get('accuracy', 0)
        },
        'total_alerts': 0,
        'critical_alerts': [],
        'warning_alerts': []
    }
    
    # Aggregate alerts
    all_alerts = (
        drift_results.get('alerts', []) +
        quality_results.get('alerts', []) +
        perf_results.get('alerts', [])
    )
    
    health_report['total_alerts'] = len(all_alerts)
    
    # Classify alerts
    for alert in all_alerts:
        if '🔴' in alert or 'CRITICAL' in alert:
            health_report['critical_alerts'].append(alert)
        else:
            health_report['warning_alerts'].append(alert)
    
    # Determine overall health
    if health_report['critical_alerts']:
        health_report['overall_health'] = 'critical'
    elif health_report['warning_alerts']:
        health_report['overall_health'] = 'warning'
    else:
        health_report['overall_health'] = 'healthy'
    
    logger.info(
        f"Health report generated: {health_report['overall_health']} "
        f"({len(health_report['critical_alerts'])} critical, "
        f"{len(health_report['warning_alerts'])} warning)"
    )
    
    # Save report
    _save_health_report(health_report)
    
    # Send summary notification
    _send_health_summary(health_report)
    
    return health_report


def _save_health_report(report: Dict[str, Any]):
    """Save health report to storage."""
    logger.info(f"Saving health report: {report['overall_health']}")
    # Would save to S3/database here


def _send_health_summary(report: Dict[str, Any]):
    """Send health summary notification."""
    if report['overall_health'] == 'critical':
        logger.critical(
            f"🚨 CRITICAL HEALTH STATUS\n"
            f"Drift: {report['drift_summary']['critical']} critical\n"
            f"Quality: {report['quality_summary']['missing_violations']} violations\n"
            f"Performance: {'DEGRADED' if report['performance_summary']['degradation'] else 'OK'}"
        )
    elif report['overall_health'] == 'warning':
        logger.warning(
            f"⚠️ WARNING HEALTH STATUS\n"
            f"Drift: {report['drift_summary']['warning']} warnings\n"
            f"Quality: {report['quality_summary']['range_violations']} violations"
        )
    else:
        logger.info("✅ System health: GOOD")


# Define the DAG
with DAG(
    'feature_health_check',
    default_args=default_args,
    description='Hourly feature drift and quality monitoring',
    schedule_interval='0 * * * *',  # Every hour
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['monitoring', 'drift', 'quality', 'hourly'],
) as dag:
    
    # Task 1: Detect feature drift
    drift_task = PythonOperator(
        task_id='detect_feature_drift',
        python_callable=detect_feature_drift,
        provide_context=True,
    )
    
    # Task 2: Check feature quality
    quality_task = PythonOperator(
        task_id='check_feature_quality',
        python_callable=check_feature_quality,
        provide_context=True,
    )
    
    # Task 3: Monitor model performance
    performance_task = PythonOperator(
        task_id='monitor_model_performance',
        python_callable=monitor_model_performance,
        provide_context=True,
    )
    
    # Task 4: Generate health report
    report_task = PythonOperator(
        task_id='generate_health_report',
        python_callable=generate_health_report,
        provide_context=True,
    )
    
    # Task dependencies (parallel monitoring, then report)
    [drift_task, quality_task, performance_task] >> report_task
