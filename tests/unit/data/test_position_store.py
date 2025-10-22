"""
Unit tests for position storage layer.

Tests abstract interface, JSON implementation, and mock implementation.
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

from src.bouncehunter.data.position_store import (
    PositionStore,
    JSONPositionStore,
    MockPositionStore
)


class TestJSONPositionStore:
    """Test JSON file-based position store."""
    
    @pytest.fixture
    def temp_store(self):
        """Create temporary JSON store for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'trades': []}, f)  # Changed from 'positions'
            temp_path = f.name
        
        store = JSONPositionStore(temp_path)
        yield store
        
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    def test_get_active_positions_empty(self, temp_store):
        """Test getting active positions from empty store."""
        positions = temp_store.get_active_positions()
        assert positions == []
    
    def test_get_active_positions_filters_correctly(self, temp_store):
        """Test that get_active_positions only returns active trades."""
        # Manually add test data
        test_positions = [
            {'ticker': 'ACTIVE1', 'status': 'active'},
            {'ticker': 'ACTIVE2', 'status': 'active'},
            {'ticker': 'CLOSED1', 'status': 'closed'},
            {'ticker': 'STOPPED', 'status': 'stopped_out'}
        ]
        
        # Write directly to file
        with open(temp_store.file_path, 'w') as f:
            json.dump({'trades': test_positions}, f)  # Changed from 'positions'
        
        active = temp_store.get_active_positions()
        
        assert len(active) == 2
        assert all(p['status'] == 'active' for p in active)
        assert {p['ticker'] for p in active} == {'ACTIVE1', 'ACTIVE2'}
    
    def test_get_position_by_ticker(self, temp_store):
        """Test getting specific position by ticker."""
        # Add test data
        test_positions = [
            {'ticker': 'AAPL', 'status': 'active', 'entry_price': 150.0},
            {'ticker': 'TSLA', 'status': 'active', 'entry_price': 200.0}
        ]
        
        with open(temp_store.file_path, 'w') as f:
            json.dump({'trades': test_positions}, f)
        
        position = temp_store.get_position('AAPL')
        
        assert position is not None
        assert position['ticker'] == 'AAPL'
        assert position['entry_price'] == 150.0
    
    def test_get_position_not_found(self, temp_store):
        """Test getting non-existent position returns None."""
        position = temp_store.get_position('NONEXISTENT')
        assert position is None
    
    def test_update_position_success(self, temp_store):
        """Test updating existing position."""
        # Add test data
        test_positions = [
            {
                'ticker': 'TEST',
                'status': 'active',
                'entry_price': 10.0,
                'exit_tiers': {}
            }
        ]
        
        with open(temp_store.file_path, 'w') as f:
            json.dump({'trades': test_positions}, f)
        
        # Update position
        updates = {
            'exit_tiers': {
                'tier1': {
                    'executed': True,
                    'exit_price': 10.50,
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
        }
        
        temp_store.update_position('TEST', updates)
        
        # Verify update
        position = temp_store.get_position('TEST')
        assert position['exit_tiers']['tier1']['executed'] is True
        assert position['exit_tiers']['tier1']['exit_price'] == 10.50
    
    def test_update_position_not_found(self, temp_store):
        """Test updating non-existent position raises error."""
        with pytest.raises(ValueError, match="Active position not found"):
            temp_store.update_position('NONEXISTENT', {'status': 'closed'})
    
    def test_get_all_positions(self, temp_store):
        """Test getting all positions regardless of status."""
        test_positions = [
            {'ticker': 'POS1', 'status': 'active'},
            {'ticker': 'POS2', 'status': 'closed'},
            {'ticker': 'POS3', 'status': 'active'}
        ]
        
        with open(temp_store.file_path, 'w') as f:
            json.dump({'trades': test_positions}, f)
        
        all_positions = temp_store.get_all_positions()
        
        assert len(all_positions) == 3
        assert {p['ticker'] for p in all_positions} == {'POS1', 'POS2', 'POS3'}
    
    def test_handles_corrupted_json(self):
        """Test store handles corrupted JSON gracefully."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('INVALID JSON {{{')
            temp_path = f.name
        
        try:
            store = JSONPositionStore(temp_path)
            
            # Should return empty list instead of crashing
            positions = store.get_active_positions()
            assert positions == []
        finally:
            Path(temp_path).unlink()
    
    def test_auto_creates_missing_file(self):
        """Test store auto-creates file if missing."""
        temp_path = Path(tempfile.gettempdir()) / 'test_auto_create.json'
        
        # Ensure file doesn't exist
        temp_path.unlink(missing_ok=True)
        
        try:
            store = JSONPositionStore(str(temp_path))
            positions = store.get_active_positions()
            
            # Should create empty file and return empty list
            assert temp_path.exists()
            assert positions == []
        finally:
            temp_path.unlink(missing_ok=True)


class TestMockPositionStore:
    """Test mock position store for testing."""
    
    def test_mock_store_empty_initialization(self):
        """Test mock store with empty initial data."""
        store = MockPositionStore()
        
        positions = store.get_active_positions()
        assert positions == []
    
    def test_mock_store_with_initial_data(self):
        """Test mock store with initial positions."""
        initial_positions = [
            {'ticker': 'MOCK1', 'status': 'active'},
            {'ticker': 'MOCK2', 'status': 'active'}
        ]
        
        store = MockPositionStore(initial_positions)
        
        active = store.get_active_positions()
        assert len(active) == 2
    
    def test_mock_store_add_position_helper(self):
        """Test add_position() helper method."""
        store = MockPositionStore()
        
        position = {
            'ticker': 'TEST',
            'status': 'active',
            'entry_price': 5.0
        }
        
        store.add_position(position)
        
        retrieved = store.get_position('TEST')
        assert retrieved == position
    
    def test_mock_store_same_interface_as_json(self):
        """Test that MockPositionStore has same interface as JSONPositionStore."""
        mock_store = MockPositionStore([
            {'ticker': 'TEST', 'status': 'active', 'value': 100}
        ])
        
        # Test all interface methods work
        active = mock_store.get_active_positions()
        assert len(active) == 1
        
        position = mock_store.get_position('TEST')
        assert position is not None
        
        mock_store.update_position('TEST', {'value': 200})
        updated = mock_store.get_position('TEST')
        assert updated['value'] == 200
        
        all_positions = mock_store.get_all_positions()
        assert len(all_positions) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
