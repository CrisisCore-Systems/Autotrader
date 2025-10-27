"""
Position storage interface and implementation.

Provides abstraction over paper_trades.json for position tracking.
Implements atomic read-modify-write operations to prevent data corruption.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod

# File locking is Unix-only, graceful fallback on Windows
try:
    import fcntl
    HAS_FCNTL = True
except (ImportError, AttributeError):
    HAS_FCNTL = False


class PositionStore(ABC):
    """Abstract interface for position storage."""
    
    @abstractmethod
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """
        Get all active positions.
        
        Returns:
            List of position dictionaries with status='active'
        """
        pass
    
    @abstractmethod
    def get_position(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get specific position by ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Position dictionary or None if not found
        """
        pass
    
    @abstractmethod
    def update_position(self, ticker: str, updates: Dict[str, Any]) -> None:
        """
        Update position with new data.
        
        Args:
            ticker: Stock ticker symbol
            updates: Dictionary of fields to update
            
        Raises:
            ValueError: If position not found
        """
        pass
    
    @abstractmethod
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all positions (active and closed)."""
        pass


class JSONPositionStore(PositionStore):
    """
    Position store implementation using JSON file.
    
    Implements file locking to prevent concurrent access issues.
    
    Attributes:
        file_path: Path to paper_trades.json
    """
    
    def __init__(self, file_path: str):
        """
        Initialize position store.
        
        Args:
            file_path: Path to paper_trades.json file
        """
        self.file_path = Path(file_path)
        
        # Create file with empty structure if doesn't exist
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_data({"trades": [], "metadata": {}})
    
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Get all active positions."""
        data = self._read_data()
        trades = data.get('trades', [])
        return [t for t in trades if t.get('status') == 'active']
    
    def get_position(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get specific position by ticker."""
        positions = self.get_active_positions()
        for position in positions:
            if position.get('ticker') == ticker:
                return position
        return None
    
    def update_position(self, ticker: str, updates: Dict[str, Any]) -> None:
        """
        Update position atomically.
        
        Args:
            ticker: Stock ticker symbol
            updates: Dictionary of updates to apply
            
        Raises:
            ValueError: If position not found
        """
        data = self._read_data()
        trades = data.get('trades', [])
        
        # Find and update position
        updated = False
        for trade in trades:
            if trade.get('ticker') == ticker and trade.get('status') == 'active':
                trade.update(updates)
                trade['last_updated'] = datetime.now().isoformat()
                updated = True
                break
        
        if not updated:
            raise ValueError(f"Active position not found for ticker: {ticker}")
        
        # Write back atomically
        self._write_data(data)
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all positions."""
        data = self._read_data()
        return data.get('trades', [])
    
    def _read_data(self) -> Dict[str, Any]:
        """
        Read data from JSON file with locking.
        
        Returns:
            Data dictionary
        """
        try:
            with open(self.file_path, 'r') as f:
                # Acquire shared lock for reading (if available)
                if HAS_FCNTL:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    except OSError:
                        pass
                
                data = json.load(f)
                
                if HAS_FCNTL:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                
                return data
        except json.JSONDecodeError:
            # Corrupted file, return empty structure
            return {"trades": [], "metadata": {}}
        except FileNotFoundError:
            return {"trades": [], "metadata": {}}
    
    def _write_data(self, data: Dict[str, Any]) -> None:
        """
        Write data to JSON file with locking.
        
        Args:
            data: Data dictionary to write
        """
        # Write to temp file first, then atomic rename
        temp_path = self.file_path.with_suffix('.tmp')
        
        with open(temp_path, 'w') as f:
            # Acquire exclusive lock for writing (if available)
            if HAS_FCNTL:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except OSError:
                    pass
            
            json.dump(data, f, indent=2)
            
            if HAS_FCNTL:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
        
        # Atomic rename
        temp_path.replace(self.file_path)


class MockPositionStore(PositionStore):
    """
    Mock position store for testing.
    
    Stores positions in memory, no file I/O.
    """
    
    def __init__(self, initial_positions: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize mock store.
        
        Args:
            initial_positions: Optional list of positions to start with
        """
        self.positions = initial_positions or []
    
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Get all active positions."""
        return [p for p in self.positions if p.get('status') == 'active']
    
    def get_position(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get specific position by ticker."""
        for position in self.positions:
            if position.get('ticker') == ticker and position.get('status') == 'active':
                return position
        return None
    
    def update_position(self, ticker: str, updates: Dict[str, Any]) -> None:
        """Update position."""
        for position in self.positions:
            if position.get('ticker') == ticker and position.get('status') == 'active':
                position.update(updates)
                return
        raise ValueError(f"Active position not found for ticker: {ticker}")
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all positions."""
        return self.positions.copy()
    
    def add_position(self, position: Dict[str, Any]) -> None:
        """Add position (test helper)."""
        self.positions.append(position)
