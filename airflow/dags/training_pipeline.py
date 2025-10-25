"""
Training Pipeline DAG for AutoTrader
Weekly model training with promotion gates and validation.

Schedule: Weekly (Sunday 3:00 AM UTC)
SLA: 6 hours
"""

from datetime import datetime, timedelta
from typing import Dict, Any
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.dates import days_ago
from airflow.models import Variable

# Configure logging
logger = logging.getLogger(__name__)

# Default arguments
default_args = {
    'owner': 'autotrader',
    'depends_on_past': False,
    'email': ['alerts@autotrader.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=30),
    'sla': timedelta(hours=6),
}


def prepare_training_data(**context) -> Dict[str, Any]:
    """
    Load and prepare training data from feature store.
    
    Returns:
        Dict with data preparation statistics
    """
    from autotrader.features.feature_store import FeatureStore
    from sklearn.model_selection import TimeSeriesSplit
    
    execution_date = context['execution_date']
    logger.info(f"Preparing training data for {execution_date}")
    
    prep_stats = {
        'execution_date': execution_date.isoformat(),
        'total_samples': 0,
        'train_samples': 0,
        'val_samples': 0,
        'test_samples': 0,
        'features_count': 0,
        'errors': []
    }
    
    try:
        # Load data from feature store
        feature_store = FeatureStore()
        
        # Get lookback period from config
        lookback_days = Variable.get("training_lookback_days", default_var=90)
        start_date = execution_date - timedelta(days=lookback_days)
        
        # Load features and labels
        data = feature_store.load_training_data(
            start_date=start_date,
            end_date=execution_date
        )
        
        prep_stats['total_samples'] = len(data)
        prep_stats['features_count'] = len(data.columns) - 1  # Exclude target
        
        # Time series split
        tscv = TimeSeriesSplit(n_splits=5)
        train_idx, test_idx = list(tscv.split(data))[-1]
        
        # Further split train into train/validation
        train_data = data.iloc[train_idx]
        test_data = data.iloc[test_idx]
        
        val_split = int(len(train_data) * 0.8)
        train_final = train_data.iloc[:val_split]
        val_data = train_data.iloc[val_split:]
        
        prep_stats['train_samples'] = len(train_final)
        prep_stats['val_samples'] = len(val_data)
        prep_stats['test_samples'] = len(test_data)
        
        # Save splits for training task
        feature_store.save_splits(
            train_data=train_final,
            val_data=val_data,
            test_data=test_data,
            execution_date=execution_date
        )
        
        logger.info(
            f"Prepared data: {prep_stats['train_samples']} train, "
            f"{prep_stats['val_samples']} val, {prep_stats['test_samples']} test"
        )
    
    except Exception as e:
        logger.error(f"Data preparation error: {e}")
        prep_stats['errors'].append(str(e))
        raise
    
    return prep_stats


def train_models(**context) -> Dict[str, Any]:
    """
    Train models using prepared data.
    
    Uses Phase 4 model training pipeline.
    
    Returns:
        Dict with training statistics
    """
    from autotrader.models.model_trainer import ModelTrainer
    from autotrader.features.feature_store import FeatureStore
    
    execution_date = context['execution_date']
    
    logger.info("Starting model training")
    
    training_stats = {
        'models_trained': 0,
        'best_model': None,
        'cv_scores': {},
        'training_time_seconds': 0,
        'errors': []
    }
    
    try:
        # Load splits
        feature_store = FeatureStore()
        train_data, val_data, _ = feature_store.load_splits(execution_date)
        
        # Initialize trainer
        trainer = ModelTrainer()
        
        # Train models with cross-validation
        start_time = datetime.utcnow()
        results = trainer.train_with_cv(
            train_data=train_data,
            val_data=val_data,
            n_folds=5
        )
        end_time = datetime.utcnow()
        
        training_stats['models_trained'] = len(results['models'])
        training_stats['best_model'] = results['best_model_name']
        training_stats['cv_scores'] = results['cv_scores']
        training_stats['training_time_seconds'] = (
            (end_time - start_time).total_seconds()
        )
        
        # Save best model
        best_model = results['best_model']
        model_path = trainer.save_model(
            model=best_model,
            version=execution_date.strftime('%Y%m%d_%H%M%S')
        )
        
        training_stats['model_path'] = model_path
        
        logger.info(
            f"Trained {training_stats['models_trained']} models. "
            f"Best: {training_stats['best_model']}"
        )
    
    except Exception as e:
        logger.error(f"Model training error: {e}")
        training_stats['errors'].append(str(e))
        raise
    
    return training_stats


def evaluate_models(**context) -> Dict[str, Any]:
    """
    Evaluate trained models on test data.
    
    Generates performance metrics and model cards.
    
    Returns:
        Dict with evaluation results
    """
    from autotrader.models.model_evaluator import ModelEvaluator
    from autotrader.features.feature_store import FeatureStore
    
    ti = context['ti']
    training_stats = ti.xcom_pull(task_ids='train_models')
    execution_date = context['execution_date']
    
    logger.info("Evaluating models")
    
    eval_results = {
        'sharpe_ratio': 0.0,
        'max_drawdown': 0.0,
        'win_rate': 0.0,
        'total_return': 0.0,
        'num_trades': 0,
        'passed_thresholds': False,
        'errors': []
    }
    
    try:
        # Load test data and model
        feature_store = FeatureStore()
        _, _, test_data = feature_store.load_splits(execution_date)
        
        evaluator = ModelEvaluator()
        model = evaluator.load_model(training_stats['model_path'])
        
        # Generate predictions
        predictions = model.predict(test_data)
        
        # Calculate metrics
        metrics = evaluator.calculate_metrics(
            predictions=predictions,
            actuals=test_data['target']
        )
        
        eval_results.update(metrics)
        
        # Generate model card
        model_card = evaluator.generate_model_card(
            model=model,
            metrics=metrics,
            training_stats=training_stats
        )
        
        # Save model card
        evaluator.save_model_card(model_card, execution_date)
        
        logger.info(f"Evaluation complete: Sharpe={metrics['sharpe_ratio']:.2f}")
    
    except Exception as e:
        logger.error(f"Model evaluation error: {e}")
        eval_results['errors'].append(str(e))
        raise
    
    return eval_results


def validate_model(**context) -> Dict[str, Any]:
    """
    Validate model meets promotion criteria.
    
    Promotion gates:
    - Sharpe ratio > 2.0
    - Max drawdown < 15%
    - Win rate > 55%
    - Backtest PnL > baseline + 10%
    
    Returns:
        Dict with validation results
    """
    ti = context['ti']
    eval_results = ti.xcom_pull(task_ids='evaluate_models')
    
    logger.info("Validating model")
    
    validation_results = {
        'passed': False,
        'gate_results': {},
        'reasons': []
    }
    
    # Define promotion gates
    gates = {
        'sharpe_ratio': {
            'value': eval_results['sharpe_ratio'],
            'threshold': 2.0,
            'operator': '>'
        },
        'max_drawdown': {
            'value': abs(eval_results['max_drawdown']),
            'threshold': 0.15,
            'operator': '<'
        },
        'win_rate': {
            'value': eval_results['win_rate'],
            'threshold': 0.55,
            'operator': '>'
        },
        'min_trades': {
            'value': eval_results['num_trades'],
            'threshold': 100,
            'operator': '>'
        }
    }
    
    # Check each gate
    all_passed = True
    for gate_name, gate_config in gates.items():
        value = gate_config['value']
        threshold = gate_config['threshold']
        operator = gate_config['operator']
        
        if operator == '>':
            passed = value > threshold
        elif operator == '<':
            passed = value < threshold
        else:
            passed = value >= threshold
        
        validation_results['gate_results'][gate_name] = {
            'passed': passed,
            'value': value,
            'threshold': threshold
        }
        
        if not passed:
            all_passed = False
            validation_results['reasons'].append(
                f"{gate_name}: {value:.3f} {operator} {threshold:.3f} failed"
            )
            logger.warning(f"Gate failed: {gate_name}")
    
    validation_results['passed'] = all_passed
    
    if all_passed:
        logger.info("✅ All promotion gates passed!")
    else:
        logger.warning(f"❌ Promotion gates failed: {validation_results['reasons']}")
        raise ValueError(f"Model validation failed: {validation_results['reasons']}")
    
    return validation_results


def promote_model(**context) -> Dict[str, Any]:
    """
    Promote model to staging environment.
    
    Updates model registry and triggers deployment.
    
    Returns:
        Dict with promotion results
    """
    from autotrader.models.model_registry import ModelRegistry
    
    ti = context['ti']
    training_stats = ti.xcom_pull(task_ids='train_models')
    eval_results = ti.xcom_pull(task_ids='evaluate_models')
    validation_results = ti.xcom_pull(task_ids='validate_model')
    execution_date = context['execution_date']
    
    logger.info("Promoting model to staging")
    
    promotion_results = {
        'model_version': None,
        'registry_id': None,
        'promoted_at': datetime.utcnow().isoformat(),
        'errors': []
    }
    
    try:
        # Register model
        registry = ModelRegistry()
        
        model_version = execution_date.strftime('%Y%m%d_%H%M%S')
        
        registry_id = registry.register_model(
            model_path=training_stats['model_path'],
            version=model_version,
            metrics=eval_results,
            validation=validation_results,
            stage='staging'
        )
        
        promotion_results['model_version'] = model_version
        promotion_results['registry_id'] = registry_id
        
        logger.info(f"Model promoted: version={model_version}, id={registry_id}")
        
        # Send notification
        _send_promotion_notification(
            model_version=model_version,
            metrics=eval_results
        )
    
    except Exception as e:
        logger.error(f"Model promotion error: {e}")
        promotion_results['errors'].append(str(e))
        raise
    
    return promotion_results


def _send_promotion_notification(model_version: str, metrics: Dict[str, Any]):
    """Send notification about model promotion."""
    logger.info(
        f"📢 Model {model_version} promoted to staging!\n"
        f"Sharpe: {metrics['sharpe_ratio']:.2f}\n"
        f"Max DD: {metrics['max_drawdown']:.2%}\n"
        f"Win Rate: {metrics['win_rate']:.2%}\n"
        f"Trades: {metrics['num_trades']}"
    )
    # Would send Slack/email notification here


# Define the DAG
with DAG(
    'training_pipeline',
    default_args=default_args,
    description='Weekly model training and validation',
    schedule_interval='0 3 * * 0',  # Sunday 3:00 AM UTC
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=['training', 'ml', 'weekly'],
) as dag:
    
    # Task 1: Prepare training data
    prepare_task = PythonOperator(
        task_id='prepare_training_data',
        python_callable=prepare_training_data,
        provide_context=True,
    )
    
    # Task 2: Train models
    train_task = PythonOperator(
        task_id='train_models',
        python_callable=train_models,
        provide_context=True,
    )
    
    # Task 3: Evaluate models
    evaluate_task = PythonOperator(
        task_id='evaluate_models',
        python_callable=evaluate_models,
        provide_context=True,
    )
    
    # Task 4: Validate against promotion gates
    validate_task = PythonOperator(
        task_id='validate_model',
        python_callable=validate_model,
        provide_context=True,
    )
    
    # Task 5: Promote to staging
    promote_task = PythonOperator(
        task_id='promote_model',
        python_callable=promote_model,
        provide_context=True,
    )
    
    # Task 6: Trigger deployment DAG (if promotion successful)
    trigger_deployment = TriggerDagRunOperator(
        task_id='trigger_deployment',
        trigger_dag_id='deployment_pipeline',
        wait_for_completion=False,
        conf={'model_version': '{{ ti.xcom_pull(task_ids="promote_model")["model_version"] }}'},
    )
    
    # Task dependencies
    (prepare_task >> train_task >> evaluate_task >> 
     validate_task >> promote_task >> trigger_deployment)
