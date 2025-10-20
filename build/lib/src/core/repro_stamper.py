"""Reproducibility stamping for AutoTrader outputs.

Provides cryptographic stamps to ensure reproducibility of scan results.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReproStamp:
    """Reproducibility stamp containing all information needed to reproduce a scan.
    
    This stamp ensures that scan results can be reproduced by capturing:
    - Input data hashes
    - Configuration state
    - Code version
    - Random seed
    - Execution environment
    """
    
    # Core identification
    timestamp: str
    stamp_version: str = "1.0.0"
    
    # Code version
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    git_dirty: bool = False
    code_hash: Optional[str] = None
    
    # Input hashes
    input_hashes: Dict[str, str] = field(default_factory=dict)
    config_hash: Optional[str] = None
    
    # Execution environment
    python_version: Optional[str] = None
    platform: Optional[str] = None
    hostname: Optional[str] = None
    
    # Randomness control
    random_seed: Optional[int] = None
    
    # Dependencies (optional)
    dependency_hashes: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)
    
    def get_composite_hash(self) -> str:
        """Get composite hash of all stamp components.
        
        Returns:
            SHA256 hash of stamp (first 16 chars)
        """
        # Create deterministic string representation
        stamp_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(stamp_str.encode()).hexdigest()[:16]


class ReproStamper:
    """Creates reproducibility stamps for scan outputs."""
    
    def __init__(self, workspace_root: Optional[Path] = None):
        """Initialize stamper.
        
        Args:
            workspace_root: Root directory of workspace (for git info)
        """
        self.workspace_root = workspace_root or Path.cwd()
        self._git_cache: Optional[Dict[str, Any]] = None  # Cache git info
    
    def create_stamp(
        self,
        input_files: Optional[List[Path]] = None,
        config_data: Optional[Dict[str, Any]] = None,
        random_seed: Optional[int] = None,
        include_dependencies: bool = False,
    ) -> ReproStamp:
        """Create reproducibility stamp.
        
        Args:
            input_files: List of input file paths to hash
            config_data: Configuration dictionary to hash
            random_seed: Random seed used in execution
            include_dependencies: Whether to include dependency hashes
        
        Returns:
            ReproStamp instance
        """
        stamp = ReproStamp(
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        
        # Git information (cached for performance)
        self._add_git_info(stamp)
        
        # Input file hashes
        if input_files:
            stamp.input_hashes = self._hash_files(input_files)
        
        # Config hash
        if config_data is not None:
            stamp.config_hash = self._hash_dict(config_data)
        
        # Environment info
        self._add_environment_info(stamp)
        
        # Random seed
        stamp.random_seed = random_seed
        
        # Dependencies (optional, can be expensive)
        if include_dependencies:
            stamp.dependency_hashes = self._hash_dependencies()
        
        logger.info(f"✅ Created reproducibility stamp: {stamp.get_composite_hash()}")
        
        return stamp
    
    def _get_git_info_cached(self) -> Dict[str, Any]:
        """Get git information with caching for performance.
        
        Returns:
            Dictionary with git info
        """
        if self._git_cache is not None:
            return self._git_cache
        
        git_info = {
            "commit": None,
            "branch": None,
            "dirty": False,
            "code_hash": None,
        }
        
        try:
            # Get git commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                git_info["commit"] = result.stdout.strip()
            
            # Get git branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                git_info["branch"] = result.stdout.strip()
            
            # Check if working directory is dirty
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                git_info["dirty"] = bool(result.stdout.strip())
            
            # If dirty, compute hash of tracked files
            if git_info["dirty"]:
                git_info["code_hash"] = self._hash_codebase()
        
        except Exception as e:
            logger.warning(f"Failed to get git info: {e}")
        
        # Cache for future calls
        self._git_cache = git_info
        return git_info
    
    def _add_git_info(self, stamp: ReproStamp) -> None:
        """Add git information to stamp.
        
        Args:
            stamp: Stamp to update
        """
        git_info = self._get_git_info_cached()
        stamp.git_commit = git_info["commit"]
        stamp.git_branch = git_info["branch"]
        stamp.git_dirty = git_info["dirty"]
        stamp.code_hash = git_info["code_hash"]
    
    def _hash_codebase(self) -> str:
        """Hash the codebase (tracked files only).
        
        Returns:
            SHA256 hash of codebase
        """
        try:
            # Get list of tracked files
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                return "unknown"
            
            files = [
                self.workspace_root / f.strip()
                for f in result.stdout.split('\n')
                if f.strip()
            ]
            
            # Hash all files
            hasher = hashlib.sha256()
            for file_path in sorted(files):
                if file_path.exists() and file_path.is_file():
                    with open(file_path, 'rb') as f:
                        hasher.update(f.read())
            
            return hasher.hexdigest()[:16]
        
        except Exception as e:
            logger.warning(f"Failed to hash codebase: {e}")
            return "unknown"
    
    def _hash_files(self, file_paths: List[Path]) -> Dict[str, str]:
        """Hash input files.
        
        Args:
            file_paths: List of file paths
        
        Returns:
            Dictionary mapping file paths to hashes
        """
        hashes = {}
        
        for file_path in file_paths:
            try:
                if file_path.exists() and file_path.is_file():
                    with open(file_path, 'rb') as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()[:16]
                    hashes[str(file_path)] = file_hash
                else:
                    hashes[str(file_path)] = "not_found"
            except Exception as e:
                logger.warning(f"Failed to hash {file_path}: {e}")
                hashes[str(file_path)] = "error"
        
        return hashes
    
    def _hash_dict(self, data: Dict[str, Any]) -> str:
        """Hash a dictionary.
        
        Args:
            data: Dictionary to hash
        
        Returns:
            SHA256 hash
        """
        try:
            # Convert to JSON string (sorted keys for determinism)
            json_str = json.dumps(data, sort_keys=True)
            return hashlib.sha256(json_str.encode()).hexdigest()[:16]
        except Exception as e:
            logger.warning(f"Failed to hash config: {e}")
            return "unknown"
    
    def _add_environment_info(self, stamp: ReproStamp) -> None:
        """Add environment information to stamp.
        
        Args:
            stamp: Stamp to update
        """
        import sys
        import platform
        
        stamp.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        stamp.platform = platform.platform()
        stamp.hostname = os.environ.get("HOSTNAME") or platform.node()
    
    def _hash_dependencies(self) -> Dict[str, str]:
        """Hash installed dependencies.
        
        Returns:
            Dictionary mapping package names to versions
        """
        try:
            import pkg_resources
            
            hashes = {}
            for dist in pkg_resources.working_set:
                # Store version instead of hash for readability
                hashes[dist.project_name] = dist.version
            
            return hashes
        
        except Exception as e:
            logger.warning(f"Failed to get dependency info: {e}")
            return {}
    
    def validate_stamp(
        self,
        stamp: ReproStamp,
        input_files: Optional[List[Path]] = None,
        config_data: Optional[Dict[str, Any]] = None,
        strict: bool = False,
    ) -> tuple[bool, List[str]]:
        """Validate a stamp against current state.
        
        Args:
            stamp: Stamp to validate
            input_files: Input files to check against
            config_data: Config to check against
            strict: Whether to enforce strict validation (including dirty state)
        
        Returns:
            Tuple of (valid, list of validation errors)
        """
        errors = []
        
        # Validate git commit
        if stamp.git_commit:
            git_info = self._get_git_info_cached()
            
            if git_info["commit"] != stamp.git_commit:
                errors.append(
                    f"Git commit mismatch: "
                    f"expected {stamp.git_commit}, got {git_info['commit']}"
                )
            
            if strict and git_info["dirty"] and not stamp.git_dirty:
                errors.append("Working directory is dirty (strict mode)")
        
        # Validate input hashes
        if input_files and stamp.input_hashes:
            current_hashes = self._hash_files(input_files)
            for file_path, expected_hash in stamp.input_hashes.items():
                current_hash = current_hashes.get(file_path)
                if current_hash != expected_hash:
                    errors.append(
                        f"Input file hash mismatch: {file_path} "
                        f"(expected {expected_hash}, got {current_hash})"
                    )
        
        # Validate config hash
        if config_data and stamp.config_hash:
            current_hash = self._hash_dict(config_data)
            if current_hash != stamp.config_hash:
                errors.append(
                    f"Config hash mismatch: "
                    f"expected {stamp.config_hash}, got {current_hash}"
                )
        
        valid = len(errors) == 0
        
        if valid:
            logger.info("✅ Stamp validation passed")
        else:
            logger.warning(f"❌ Stamp validation failed: {len(errors)} error(s)")
            for error in errors:
                logger.warning(f"  - {error}")
        
        return valid, errors


def create_repro_stamp(
    input_files: Optional[List[Path]] = None,
    config_data: Optional[Dict[str, Any]] = None,
    random_seed: Optional[int] = None,
    workspace_root: Optional[Path] = None,
) -> ReproStamp:
    """Create a reproducibility stamp.
    
    Convenience function.
    
    Args:
        input_files: Input files to hash
        config_data: Config to hash
        random_seed: Random seed
        workspace_root: Workspace root
    
    Returns:
        ReproStamp instance
    """
    stamper = ReproStamper(workspace_root)
    return stamper.create_stamp(input_files, config_data, random_seed)


def add_repro_stamp_to_output(
    output: Dict[str, Any],
    input_files: Optional[List[Path]] = None,
    config_data: Optional[Dict[str, Any]] = None,
    random_seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Add reproducibility stamp to output data.
    
    Args:
        output: Output dictionary
        input_files: Input files
        config_data: Config data
        random_seed: Random seed
    
    Returns:
        Output with repro_stamp field
    """
    stamp = create_repro_stamp(input_files, config_data, random_seed)
    output["repro_stamp"] = stamp.to_dict()
    output["repro_hash"] = stamp.get_composite_hash()
    return output


if __name__ == "__main__":
    # Test the stamper
    print("\n" + "=" * 80)
    print("REPRODUCIBILITY STAMPER TEST")
    print("=" * 80)
    
    # Create test stamp
    stamper = ReproStamper()
    
    test_config = {
        "scanner": {"liquidity_threshold": 50000},
        "alerts": {"enabled": True},
    }
    
    stamp = stamper.create_stamp(
        config_data=test_config,
        random_seed=42,
    )
    
    print("\nStamp created:")
    print(stamp.to_json())
    
    print(f"\nComposite hash: {stamp.get_composite_hash()}")
    
    # Validate stamp
    valid, errors = stamper.validate_stamp(stamp, config_data=test_config)
    
    print(f"\nValidation: {'✅ PASS' if valid else '❌ FAIL'}")
    if errors:
        print("Errors:")
        for error in errors:
            print(f"  - {error}")
    
    print("\n" + "=" * 80 + "\n")
