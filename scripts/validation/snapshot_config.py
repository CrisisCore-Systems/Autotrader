"""
Snapshot agent configurations and hyperparameters for validation roadmap.
Registers current state in MLflow and/or DVC metrics.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any
import yaml


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime and date objects."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def snapshot_agent_config(
    agents_config: Path,
    training_config: Path,
    feature_catalog: Path,
    output_snapshot: Path
) -> Dict[str, Any]:
    """
    Create snapshot of agent configuration, hyperparameters, and feature set.
    
    Returns:
        Dict with snapshot metadata
    """
    print("📸 Snapshotting agent configuration...")
    
    # Load configs
    with open(agents_config) as f:
        agents = yaml.safe_load(f)
    
    with open(training_config) as f:
        training = yaml.safe_load(f)
    
    # Compute hashes
    agents_hash = compute_file_hash(agents_config)
    training_hash = compute_file_hash(training_config)
    feature_catalog_hash = compute_file_hash(feature_catalog)
    
    # Extract key parameters
    snapshot = {
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'snapshot_id': f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        
        'agents': {
            'config_path': str(agents_config),
            'config_hash': agents_hash,
            'version': agents.get('version', 'unknown'),
            'last_updated': agents.get('last_updated', 'unknown'),
            'agent_count': len(agents.get('agents', {})),
            'defaults': agents.get('defaults', {}),
        },
        
        'training': {
            'config_path': str(training_config),
            'config_hash': training_hash,
            'experiment_name': training['run']['experiment_name'],
            'model_name': training['run']['model_name'],
            'hyperparameters': training['hyperparameters'],
            'tags': training['run'].get('tags', {}),
        },
        
        'features': {
            'catalog_path': str(feature_catalog),
            'catalog_hash': feature_catalog_hash,
            'catalog_size_bytes': feature_catalog.stat().st_size,
        },
        
        'git_info': _get_git_info(),
    }
    
    # Write snapshot
    output_snapshot.parent.mkdir(parents=True, exist_ok=True)
    with open(output_snapshot, 'w') as f:
        json.dump(snapshot, f, indent=2, cls=DateTimeEncoder)
    
    print(f"✅ Snapshot created: {output_snapshot}")
    print(f"   Snapshot ID: {snapshot['snapshot_id']}")
    print(f"   Agents hash: {agents_hash[:12]}...")
    print(f"   Training hash: {training_hash[:12]}...")
    print(f"   Features hash: {feature_catalog_hash[:12]}...")
    
    return snapshot


def _get_git_info() -> Dict[str, str]:
    """Get current git branch and commit."""
    import subprocess
    
    try:
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        commit = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        return {
            'branch': branch,
            'commit': commit,
            'commit_short': commit[:8],
        }
    except Exception:
        return {
            'branch': 'unknown',
            'commit': 'unknown',
            'commit_short': 'unknown',
        }


def register_to_mlflow(snapshot: Dict[str, Any], mlflow_config: Path) -> None:
    """Register snapshot to MLflow tracking."""
    try:
        import mlflow
        
        # Load MLflow config
        with open(mlflow_config) as f:
            mlflow_cfg = yaml.safe_load(f)
        
        # Use local profile by default
        profile = mlflow_cfg['profiles']['local']
        mlflow.set_tracking_uri(profile['tracking_uri'])
        mlflow.set_experiment(profile['experiment'])
        
        # Log snapshot as a run
        with mlflow.start_run(run_name=f"config_snapshot_{datetime.now().strftime('%Y%m%d')}"):
            # Log parameters
            mlflow.log_params({
                'snapshot_id': snapshot['snapshot_id'],
                'agents_hash': snapshot['agents']['config_hash'][:12],
                'training_hash': snapshot['training']['config_hash'][:12],
                'features_hash': snapshot['features']['catalog_hash'][:12],
                'git_branch': snapshot['git_info']['branch'],
                'git_commit': snapshot['git_info']['commit_short'],
            })
            
            # Log hyperparameters
            for key, value in snapshot['training']['hyperparameters'].items():
                mlflow.log_param(f"hp_{key}", value)
            
            # Log artifact (full snapshot)
            mlflow.log_dict(snapshot, "config_snapshot.json")
            
            print(f"✅ Registered to MLflow: {profile['tracking_uri']}")
            
    except ImportError:
        print("⚠️  MLflow not available - skipping MLflow registration")
    except Exception as e:
        print(f"⚠️  MLflow registration failed: {e}")


def create_dvc_metrics(snapshot: Dict[str, Any], output_metrics: Path) -> None:
    """Create DVC metrics file from snapshot."""
    
    metrics = {
        'config_snapshot': {
            'snapshot_id': snapshot['snapshot_id'],
            'timestamp': snapshot['timestamp'],
            'agents': {
                'count': snapshot['agents']['agent_count'],
                'version': snapshot['agents']['version'],
                'hash': snapshot['agents']['config_hash'][:12],
            },
            'training': {
                'learning_rate': snapshot['training']['hyperparameters']['learning_rate'],
                'batch_size': snapshot['training']['hyperparameters']['batch_size'],
                'epochs': snapshot['training']['hyperparameters']['epochs'],
                'hash': snapshot['training']['config_hash'][:12],
            },
            'features': {
                'catalog_size_kb': snapshot['features']['catalog_size_bytes'] / 1024,
                'hash': snapshot['features']['catalog_hash'][:12],
            },
            'git': {
                'branch': snapshot['git_info']['branch'],
                'commit': snapshot['git_info']['commit_short'],
            },
        }
    }
    
    output_metrics.parent.mkdir(parents=True, exist_ok=True)
    with open(output_metrics, 'w') as f:
        json.dump(metrics, f, indent=2, cls=DateTimeEncoder)
    
    print(f"✅ DVC metrics: {output_metrics}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Snapshot agent configurations')
    parser.add_argument('--agents-config', type=Path, required=True,
                       help='Path to agents.yaml')
    parser.add_argument('--training-config', type=Path, required=True,
                       help='Path to training strategy config')
    parser.add_argument('--feature-catalog', type=Path, required=True,
                       help='Path to FEATURE_CATALOG.md')
    parser.add_argument('--output', type=Path, required=True,
                       help='Output snapshot JSON')
    parser.add_argument('--mlflow-config', type=Path,
                       help='MLflow tracking config (optional)')
    parser.add_argument('--dvc-metrics', type=Path,
                       help='DVC metrics output (optional)')
    
    args = parser.parse_args()
    
    snapshot = snapshot_agent_config(
        args.agents_config,
        args.training_config,
        args.feature_catalog,
        args.output
    )
    
    if args.mlflow_config and args.mlflow_config.exists():
        register_to_mlflow(snapshot, args.mlflow_config)
    
    if args.dvc_metrics:
        create_dvc_metrics(snapshot, args.dvc_metrics)
