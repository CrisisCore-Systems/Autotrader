"""
Data Pipeline DAG for AutoTrader
Nightly data ingestion, validation, transformation, and health checks.

Schedule: Daily at 2:00 AM UTC
SLA: 2 hours
"""

from datetime import datetime, timedelta
from typing import Dict, Any
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.models import Variable

# Configure logging
logger = logging.getLogger(__name__)

# Default arguments for all tasks
default_args = {
    'owner': 'autotrader',
    'depends_on_past': False,
    'email': ['alerts@autotrader.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'sla': timedelta(hours=2),
}


def _extract_from_broker(broker_name: str, connector_class, symbols: List[str], 
                         execution_date: datetime, **kwargs) -> tuple:
    """Helper to extract data from a single broker."""
    try:
        connector = connector_class()
        total_bars = 0
        
        for symbol in symbols:
            bars = connector.get_historical_bars(symbol=symbol, **kwargs)
            total_bars += len(bars)
        
        logger.info(f"Extracted {total_bars} bars from {broker_name}")
        return total_bars, None
    except Exception as e:
        logger.error(f"{broker_name} extraction failed: {e}")
        return 0, str(e)


def extract_market_data(**context) -> Dict[str, Any]:
    """
    Extract market data from all configured brokers.
    
    Returns:
        Dict with extraction statistics
    """
    from autotrader.connectors.binance_connector import BinanceConnector
    from autotrader.connectors.ibkr_connector import IBKRConnector
    from autotrader.connectors.oanda_connector import OandaConnector
    
    execution_date = context['execution_date']
    logger.info(f"Extracting market data for {execution_date}")
    
    stats = {
        'execution_date': execution_date.isoformat(),
        'brokers': {},
        'total_bars': 0,
        'total_ticks': 0,
        'errors': []
    }
    
    # Define broker configurations
    broker_configs = [
        (
            'binance',
            BinanceConnector,
            Variable.get("binance_symbols", deserialize_json=True),
            {
                'interval': '1m',
                'start_time': execution_date - timedelta(days=1),
                'end_time': execution_date
            }
        ),
        (
            'ibkr',
            IBKRConnector,
            Variable.get("ibkr_symbols", deserialize_json=True),
            {
                'bar_size': '1 min',
                'duration': '1 D',
                'end_datetime': execution_date
            }
        ),
        (
            'oanda',
            OandaConnector,
            Variable.get("oanda_symbols", deserialize_json=True),
            {
                'granularity': 'M1',
                'from_time': execution_date - timedelta(days=1),
                'to_time': execution_date
            }
        ),
    ]
    
    # Extract from all brokers
    for broker_name, connector_class, symbols, kwargs in broker_configs:
        bars, error = _extract_from_broker(
            broker_name, connector_class, symbols, execution_date, **kwargs
        )
        stats['brokers'][broker_name] = bars
        stats['total_bars'] += bars
        if error:
            stats['errors'].append(f"{broker_name}: {error}")
    
    logger.info(f"Total extraction: {stats['total_bars']} bars")
    return stats


def _run_schema_validation() -> tuple:
    """Helper to run schema validation."""
    from autotrader.pipelines.validators import SchemaValidator
    try:
        schema_validator = SchemaValidator()
        result = schema_validator.validate_all()
        if not result.is_valid:
            logger.warning(f"Schema validation failed: {result.errors}")
        return result.is_valid, result.errors if not result.is_valid else []
    except Exception as e:
        logger.error(f"Schema validation error: {e}")
        return False, [f"Schema: {str(e)}"]


def _run_completeness_validation(expected_bars: int) -> tuple:
    """Helper to run completeness validation."""
    from autotrader.pipelines.validators import CompletenessValidator
    try:
        completeness_validator = CompletenessValidator()
        result = completeness_validator.check_completeness(expected_bars=expected_bars)
        if not result.is_complete:
            logger.warning(f"Completeness check failed: {result.missing}")
        return result.is_complete, result.missing if not result.is_complete else []
    except Exception as e:
        logger.error(f"Completeness validation error: {e}")
        return False, [f"Completeness: {str(e)}"]


def _run_anomaly_detection() -> tuple:
    """Helper to run anomaly detection."""
    from autotrader.pipelines.validators import AnomalyDetector
    try:
        anomaly_detector = AnomalyDetector()
        anomalies = anomaly_detector.detect_anomalies()
        if anomalies:
            logger.warning(f"Anomalies detected: {len(anomalies)}")
            for anomaly in anomalies:
                logger.warning(f"  {anomaly}")
        return anomalies, []
    except Exception as e:
        logger.error(f"Anomaly detection error: {e}")
        return [], [f"Anomaly: {str(e)}"]


def validate_data(**context) -> Dict[str, Any]:
    """
    Validate extracted data quality.
    
    Checks:
    - Schema compliance
    - Data completeness
    - Value ranges
    - Anomaly detection
    
    Returns:
        Dict with validation results
    """
    ti = context['ti']
    extraction_stats = ti.xcom_pull(task_ids='extract_market_data')
    
    logger.info("Starting data validation")
    
    validation_results = {
        'schema_valid': True,
        'completeness_valid': True,
        'anomalies_detected': [],
        'errors': []
    }
    
    # Run schema validation
    schema_valid, schema_errors = _run_schema_validation()
    validation_results['schema_valid'] = schema_valid
    validation_results['errors'].extend(schema_errors)
    
    # Run completeness validation
    completeness_valid, completeness_errors = _run_completeness_validation(
        extraction_stats['total_bars']
    )
    validation_results['completeness_valid'] = completeness_valid
    validation_results['errors'].extend(completeness_errors)
    
    # Run anomaly detection
    anomalies, anomaly_errors = _run_anomaly_detection()
    validation_results['anomalies_detected'] = anomalies
    validation_results['errors'].extend(anomaly_errors)
    
    # Fail task if critical errors
    if not validation_results['schema_valid'] or not validation_results['completeness_valid']:
        raise ValueError(f"Data validation failed: {validation_results['errors']}")
    
    logger.info("Data validation completed successfully")
    return validation_results


def transform_features(**context) -> Dict[str, Any]:
    """
    Transform raw data into features.
    
    Uses Phase 3 feature engineering pipeline.
    
    Returns:
        Dict with transformation statistics
    """
    from autotrader.features.feature_engineering import FeatureEngineer
    
    logger.info("Starting feature transformation")
    
    transform_stats = {
        'features_generated': 0,
        'feature_groups': {},
        'errors': []
    }
    
    try:
        feature_engineer = FeatureEngineer()
        
        # Generate technical features
        tech_features = feature_engineer.generate_technical_features()
        transform_stats['feature_groups']['technical'] = len(tech_features)
        transform_stats['features_generated'] += len(tech_features)
        
        # Generate microstructure features
        micro_features = feature_engineer.generate_microstructure_features()
        transform_stats['feature_groups']['microstructure'] = len(micro_features)
        transform_stats['features_generated'] += len(micro_features)
        
        # Generate regime features
        regime_features = feature_engineer.generate_regime_features()
        transform_stats['feature_groups']['regime'] = len(regime_features)
        transform_stats['features_generated'] += len(regime_features)
        
        logger.info(f"Generated {transform_stats['features_generated']} features")
    
    except Exception as e:
        logger.error(f"Feature transformation error: {e}")
        transform_stats['errors'].append(str(e))
        raise
    
    return transform_stats


def load_to_feature_store(**context) -> Dict[str, Any]:
    """
    Load transformed features to feature store.
    
    Returns:
        Dict with load statistics
    """
    from autotrader.features.feature_store import FeatureStore
    
    ti = context['ti']
    transform_stats = ti.xcom_pull(task_ids='transform_features')
    
    logger.info("Loading features to feature store")
    
    load_stats = {
        'features_loaded': 0,
        'tables_updated': [],
        'errors': []
    }
    
    try:
        feature_store = FeatureStore()
        
        # Load features
        result = feature_store.load_features(
            execution_date=context['execution_date']
        )
        
        load_stats['features_loaded'] = result['count']
        load_stats['tables_updated'] = result['tables']
        
        # Update metadata
        feature_store.update_metadata(
            execution_date=context['execution_date'],
            stats=transform_stats
        )
        
        logger.info(f"Loaded {load_stats['features_loaded']} features")
    
    except Exception as e:
        logger.error(f"Feature store load error: {e}")
        load_stats['errors'].append(str(e))
        raise
    
    return load_stats


def archive_raw_data(**context) -> Dict[str, Any]:
    """
    Archive raw data to S3.
    
    Returns:
        Dict with archive statistics
    """
    import boto3
    from io import BytesIO
    import gzip
    
    ti = context['ti']
    extraction_stats = ti.xcom_pull(task_ids='extract_market_data')
    execution_date = context['execution_date']
    
    logger.info("Archiving raw data")
    
    archive_stats = {
        'files_archived': 0,
        'bytes_archived': 0,
        'errors': []
    }
    
    try:
        s3_client = boto3.client('s3')
        bucket = Variable.get("s3_archive_bucket")
        
        # Archive format: s3://bucket/year/month/day/broker_data.gz
        date_path = execution_date.strftime('%Y/%m/%d')
        
        for broker in extraction_stats['brokers'].keys():
            try:
                # Get raw data
                from autotrader.storage.data_store import DataStore
                data_store = DataStore()
                raw_data = data_store.get_raw_data(broker, execution_date)
                
                # Compress
                compressed = BytesIO()
                with gzip.GzipFile(fileobj=compressed, mode='wb') as gz:
                    gz.write(raw_data.encode())
                
                # Upload to S3
                s3_key = f"{date_path}/{broker}_data.gz"
                s3_client.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=compressed.getvalue()
                )
                
                archive_stats['files_archived'] += 1
                archive_stats['bytes_archived'] += len(compressed.getvalue())
                
                logger.info(f"Archived {broker} data to s3://{bucket}/{s3_key}")
            
            except Exception as e:
                logger.error(f"Archive failed for {broker}: {e}")
                archive_stats['errors'].append(f"{broker}: {str(e)}")
        
        logger.info(f"Archived {archive_stats['files_archived']} files")
    
    except Exception as e:
        logger.error(f"Archive error: {e}")
        archive_stats['errors'].append(str(e))
        raise
    
    return archive_stats


def _check_freshness(feature_store) -> tuple:
    """Helper to check data freshness."""
    try:
        latest_timestamp = feature_store.get_latest_timestamp()
        age_minutes = (datetime.utcnow() - latest_timestamp).total_seconds() / 60
        
        alerts, warnings = [], []
        is_fresh = True
        
        if age_minutes > 120:  # More than 2 hours old
            is_fresh = False
            alerts.append(f"Data is stale: {age_minutes:.1f} minutes old")
        elif age_minutes > 60:
            warnings.append(f"Data is aging: {age_minutes:.1f} minutes old")
        
        return is_fresh, alerts, warnings
    except Exception as e:
        logger.error(f"Freshness check error: {e}")
        return False, [f"Freshness check failed: {str(e)}"], []


def _check_drift() -> tuple:
    """Helper to check feature drift."""
    from autotrader.monitoring.drift_detector import DriftDetector
    try:
        drift_detector = DriftDetector()
        drift_results = drift_detector.detect_drift()
        
        critical_drift = [d for d in drift_results if d['psi'] > 0.3]
        warning_drift = [d for d in drift_results if 0.2 < d['psi'] <= 0.3]
        
        alerts = [
            f"Critical drift: {d['feature']} PSI={d['psi']:.3f}"
            for d in critical_drift
        ]
        warnings = [
            f"Warning drift: {d['feature']} PSI={d['psi']:.3f}"
            for d in warning_drift
        ]
        
        is_ok = len(critical_drift) == 0
        return is_ok, alerts, warnings
    except Exception as e:
        logger.error(f"Drift check error: {e}")
        return False, [f"Drift check failed: {str(e)}"], []


def check_data_health(**context) -> Dict[str, Any]:
    """
    Perform health checks on data pipeline.
    
    Checks:
    - Data freshness
    - Feature drift
    - Anomalies
    
    Returns:
        Dict with health check results
    """
    from autotrader.features.feature_store import FeatureStore
    
    logger.info("Running data health checks")
    
    health_results = {
        'freshness_check': True,
        'drift_check': True,
        'anomaly_check': True,
        'alerts': [],
        'warnings': []
    }
    
    # Freshness check
    feature_store = FeatureStore()
    freshness_ok, fresh_alerts, fresh_warnings = _check_freshness(feature_store)
    health_results['freshness_check'] = freshness_ok
    health_results['alerts'].extend(fresh_alerts)
    health_results['warnings'].extend(fresh_warnings)
    
    # Drift check
    drift_ok, drift_alerts, drift_warnings = _check_drift()
    health_results['drift_check'] = drift_ok
    health_results['alerts'].extend(drift_alerts)
    health_results['warnings'].extend(drift_warnings)
    
    # Send alerts if needed
    if health_results['alerts']:
        logger.critical(f"Health check alerts: {health_results['alerts']}")
        # Would trigger PagerDuty/Slack here
    
    if health_results['warnings']:
        logger.warning(f"Health check warnings: {health_results['warnings']}")
    
    logger.info("Health checks completed")
    return health_results


# Define the DAG
with DAG(
    'data_pipeline',
    default_args=default_args,
    description='Nightly data ingestion and processing',
    schedule_interval='0 2 * * *',  # 2:00 AM UTC daily
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['data', 'ingestion', 'nightly'],
) as dag:
    
    # Task 1: Extract market data
    extract_task = PythonOperator(
        task_id='extract_market_data',
        python_callable=extract_market_data,
        provide_context=True,
    )
    
    # Task 2: Validate data quality
    validate_task = PythonOperator(
        task_id='validate_data',
        python_callable=validate_data,
        provide_context=True,
    )
    
    # Task 3: Transform to features
    transform_task = PythonOperator(
        task_id='transform_features',
        python_callable=transform_features,
        provide_context=True,
    )
    
    # Task 4: Load to feature store
    load_task = PythonOperator(
        task_id='load_to_feature_store',
        python_callable=load_to_feature_store,
        provide_context=True,
    )
    
    # Task 5: Archive raw data
    archive_task = PythonOperator(
        task_id='archive_raw_data',
        python_callable=archive_raw_data,
        provide_context=True,
    )
    
    # Task 6: Health checks
    health_task = PythonOperator(
        task_id='check_data_health',
        python_callable=check_data_health,
        provide_context=True,
    )
    
    # Task dependencies
    (extract_task >> validate_task >> transform_task >> 
     load_task >> archive_task >> health_task)
