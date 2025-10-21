"""
Intelligent Exit Management System for PennyHunter.

This module implements a tiered profit-taking strategy that enhances
swing trading by locking in profits at predetermined levels while
preserving runner potential.

Modules:
    config: Configuration management with validation
    monitor: Position monitoring orchestrator
    tier1_exit: End-of-day profit locking logic
    tier2_exit: Momentum spike capture logic
    executor: Order execution with retry
    adjustments: Intelligent parameter adjustments based on market conditions
    
Example:
    >>> from src.bouncehunter.exits import PositionMonitor
    >>> monitor = PositionMonitor.from_config('configs/intelligent_exits.yaml')
    >>> monitor.run_monitoring_cycle()
"""

__version__ = '0.2.0'
__all__ = [
    'ExitConfig',
    'ExitConfigManager',
    'PositionMonitor',
    'Tier1Exit',
    'Tier2Exit',
    'MarketConditions',
    'AdjustmentCalculator',
    'SymbolLearner',
    'MarketRegime',
    'VolatilityLevel',
    'TimeOfDayPeriod'
]
