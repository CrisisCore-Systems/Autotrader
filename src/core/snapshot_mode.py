"""Reproducibility Snapshot Mode for AutoTrader.

This module enforces immutability and determinism for reproducible analysis.
Snapshot mode pins all data sources, disables dynamic fetching, and ensures
bit-for-bit reproducibility of results.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from enum import Enum


class SnapshotMode(Enum):
    """Snapshot execution modes."""
    
    DYNAMIC = "dynamic"  # Normal mode - fetch live data
    SNAPSHOT = "snapshot"  # Snapshot mode - use pinned data only
    RECORD = "record"  # Record mode - fetch and save for future snapshots


@dataclass
class DataSnapshot:
    """Immutable data snapshot with cryptographic verification."""
    
    snapshot_id: str
    created_at: datetime
    data_hash: str  # SHA-256 of data
    source: str  # Data source identifier
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"
    
    def verify(self, data: Any) -> bool:
        """Verify data matches snapshot hash.
        
        Parameters
        ----------
        data : Any
            Data to verify against snapshot.
            
        Returns
        -------
        bool
            True if data matches snapshot hash.
        """
        computed_hash = self._compute_hash(data)
        return computed_hash == self.data_hash
    
    @staticmethod
    def _compute_hash(data: Any) -> str:
        """Compute SHA-256 hash of data."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at.isoformat(),
            "data_hash": self.data_hash,
            "source": self.source,
            "metadata": self.metadata,
            "schema_version": self.schema_version,
        }
    
    @classmethod
    def from_data(
        cls,
        data: Any,
        source: str,
        snapshot_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DataSnapshot:
        """Create snapshot from data.
        
        Parameters
        ----------
        data : Any
            Data to snapshot.
        source : str
            Source identifier (e.g., "etherscan:price", "dexscreener:token").
        snapshot_id : Optional[str]
            Custom snapshot ID, auto-generated if None.
        metadata : Optional[Dict[str, Any]]
            Additional metadata.
            
        Returns
        -------
        DataSnapshot
            New snapshot instance.
        """
        if snapshot_id is None:
            snapshot_id = f"{source.replace(':', '_')}__{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return cls(
            snapshot_id=snapshot_id,
            created_at=datetime.utcnow(),
            data_hash=cls._compute_hash(data),
            source=source,
            metadata=metadata or {},
        )


class SnapshotRegistry:
    """Central registry for managing data snapshots."""
    
    def __init__(self, snapshot_dir: Optional[Path] = None):
        """Initialize snapshot registry.
        
        Parameters
        ----------
        snapshot_dir : Optional[Path]
            Directory to store snapshots, defaults to ./snapshots
        """
        self.snapshot_dir = snapshot_dir or Path("./snapshots")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots: Dict[str, DataSnapshot] = {}
        self.mode = SnapshotMode.DYNAMIC
        self._load_snapshots()
    
    def _load_snapshots(self) -> None:
        """Load existing snapshots from disk."""
        index_path = self.snapshot_dir / "index.json"
        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    index = json.load(f)
                    for snapshot_data in index.get("snapshots", []):
                        snapshot = DataSnapshot(
                            snapshot_id=snapshot_data["snapshot_id"],
                            created_at=datetime.fromisoformat(snapshot_data["created_at"]),
                            data_hash=snapshot_data["data_hash"],
                            source=snapshot_data["source"],
                            metadata=snapshot_data.get("metadata", {}),
                            schema_version=snapshot_data.get("schema_version", "1.0"),
                        )
                        self.snapshots[snapshot.snapshot_id] = snapshot
            except Exception as e:
                print(f"Warning: Failed to load snapshot index: {e}")
    
    def _save_index(self) -> None:
        """Save snapshot index to disk."""
        index_path = self.snapshot_dir / "index.json"
        index = {
            "version": "1.0",
            "mode": self.mode.value,
            "snapshots": [s.to_dict() for s in self.snapshots.values()],
        }
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, default=str)
    
    def set_mode(self, mode: SnapshotMode) -> None:
        """Set snapshot execution mode.
        
        Parameters
        ----------
        mode : SnapshotMode
            Execution mode to use.
        """
        self.mode = mode
        print(f"Snapshot mode set to: {mode.value}")
        self._save_index()
    
    def record_snapshot(
        self,
        data: Any,
        source: str,
        snapshot_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DataSnapshot:
        """Record a new data snapshot.
        
        Parameters
        ----------
        data : Any
            Data to snapshot.
        source : str
            Source identifier.
        snapshot_id : Optional[str]
            Custom snapshot ID.
        metadata : Optional[Dict[str, Any]]
            Additional metadata.
            
        Returns
        -------
        DataSnapshot
            Created snapshot.
        """
        snapshot = DataSnapshot.from_data(data, source, snapshot_id, metadata)
        
        # Save data to disk
        data_path = self.snapshot_dir / f"{snapshot.snapshot_id}.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        
        # Register snapshot
        self.snapshots[snapshot.snapshot_id] = snapshot
        self._save_index()
        
        print(f"✓ Recorded snapshot: {snapshot.snapshot_id}")
        return snapshot
    
    def load_snapshot(self, snapshot_id: str) -> tuple[Any, DataSnapshot]:
        """Load data from snapshot.
        
        Parameters
        ----------
        snapshot_id : str
            Snapshot ID to load.
            
        Returns
        -------
        tuple[Any, DataSnapshot]
            Tuple of (data, snapshot_metadata).
            
        Raises
        ------
        ValueError
            If snapshot not found or verification fails.
        """
        if snapshot_id not in self.snapshots:
            raise ValueError(f"Snapshot not found: {snapshot_id}")
        
        snapshot = self.snapshots[snapshot_id]
        data_path = self.snapshot_dir / f"{snapshot_id}.json"
        
        if not data_path.exists():
            raise ValueError(f"Snapshot data file not found: {data_path}")
        
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Verify integrity
        if not snapshot.verify(data):
            raise ValueError(f"Snapshot verification failed: {snapshot_id}")
        
        return data, snapshot
    
    def get_snapshot_by_source(
        self,
        source: str,
        latest: bool = True,
    ) -> Optional[DataSnapshot]:
        """Get snapshot by source identifier.
        
        Parameters
        ----------
        source : str
            Source identifier to search for.
        latest : bool
            If True, return most recent snapshot for source.
            
        Returns
        -------
        Optional[DataSnapshot]
            Matching snapshot or None.
        """
        matching = [s for s in self.snapshots.values() if s.source == source]
        if not matching:
            return None
        
        if latest:
            return max(matching, key=lambda s: s.created_at)
        
        return matching[0]
    
    def enforce_snapshot_mode(
        self,
        source: str,
        fetch_fn: callable,
        *args,
        **kwargs,
    ) -> Any:
        """Enforce snapshot mode when fetching data.
        
        In SNAPSHOT mode: Load from snapshot, fail if not found.
        In RECORD mode: Fetch live and record snapshot.
        In DYNAMIC mode: Just fetch live.
        
        Parameters
        ----------
        source : str
            Data source identifier.
        fetch_fn : callable
            Function to fetch live data.
        *args, **kwargs
            Arguments passed to fetch_fn.
            
        Returns
        -------
        Any
            Fetched or loaded data.
            
        Raises
        ------
        RuntimeError
            In SNAPSHOT mode if snapshot not found.
        """
        if self.mode == SnapshotMode.SNAPSHOT:
            # Snapshot mode - must use pinned data
            snapshot = self.get_snapshot_by_source(source, latest=True)
            if snapshot is None:
                raise RuntimeError(
                    f"SNAPSHOT mode enforced but no snapshot found for source: {source}. "
                    f"Run in RECORD mode first to create snapshots."
                )
            
            data, _ = self.load_snapshot(snapshot.snapshot_id)
            print(f"✓ Loaded from snapshot: {snapshot.snapshot_id}")
            return data
        
        elif self.mode == SnapshotMode.RECORD:
            # Record mode - fetch and save
            data = fetch_fn(*args, **kwargs)
            self.record_snapshot(
                data=data,
                source=source,
                metadata={"args": str(args), "kwargs": str(kwargs)},
            )
            return data
        
        else:
            # Dynamic mode - normal operation
            return fetch_fn(*args, **kwargs)
    
    def list_snapshots(self, source: Optional[str] = None) -> list[DataSnapshot]:
        """List all snapshots, optionally filtered by source.
        
        Parameters
        ----------
        source : Optional[str]
            Filter by source identifier.
            
        Returns
        -------
        list[DataSnapshot]
            List of snapshots.
        """
        if source:
            return [s for s in self.snapshots.values() if s.source == source]
        return list(self.snapshots.values())
    
    def verify_all(self) -> Dict[str, bool]:
        """Verify integrity of all snapshots.
        
        Returns
        -------
        Dict[str, bool]
            Mapping of snapshot_id to verification result.
        """
        results = {}
        for snapshot_id in self.snapshots:
            try:
                data, snapshot = self.load_snapshot(snapshot_id)
                results[snapshot_id] = True
            except Exception as e:
                print(f"✗ Verification failed for {snapshot_id}: {e}")
                results[snapshot_id] = False
        
        return results
    
    def export_manifest(self, output_path: Optional[Path] = None) -> Path:
        """Export snapshot manifest for documentation.
        
        Parameters
        ----------
        output_path : Optional[Path]
            Output file path, defaults to snapshots/MANIFEST.md
            
        Returns
        -------
        Path
            Path to generated manifest.
        """
        if output_path is None:
            output_path = self.snapshot_dir / "MANIFEST.md"
        
        lines = [
            "# Data Snapshot Manifest",
            "",
            f"**Mode:** {self.mode.value}",
            f"**Total Snapshots:** {len(self.snapshots)}",
            f"**Generated:** {datetime.utcnow().isoformat()}",
            "",
            "## Snapshots",
            "",
        ]
        
        for snapshot in sorted(self.snapshots.values(), key=lambda s: s.created_at):
            lines.extend([
                f"### {snapshot.snapshot_id}",
                "",
                f"- **Source:** `{snapshot.source}`",
                f"- **Created:** {snapshot.created_at.isoformat()}",
                f"- **Hash:** `{snapshot.data_hash[:16]}...`",
                f"- **Schema:** {snapshot.schema_version}",
            ])
            
            if snapshot.metadata:
                lines.append(f"- **Metadata:** {json.dumps(snapshot.metadata, indent=2)}")
            
            lines.append("")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        print(f"✓ Exported manifest to: {output_path}")
        return output_path


# Global registry instance
_global_registry: Optional[SnapshotRegistry] = None


def get_snapshot_registry() -> SnapshotRegistry:
    """Get or create global snapshot registry.
    
    Returns
    -------
    SnapshotRegistry
        Global registry instance.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = SnapshotRegistry()
    return _global_registry


def enable_snapshot_mode() -> None:
    """Enable snapshot mode globally (immutable, pinned data)."""
    registry = get_snapshot_registry()
    registry.set_mode(SnapshotMode.SNAPSHOT)


def enable_record_mode() -> None:
    """Enable record mode globally (fetch and save snapshots)."""
    registry = get_snapshot_registry()
    registry.set_mode(SnapshotMode.RECORD)


def enable_dynamic_mode() -> None:
    """Enable dynamic mode globally (normal operation)."""
    registry = get_snapshot_registry()
    registry.set_mode(SnapshotMode.DYNAMIC)
