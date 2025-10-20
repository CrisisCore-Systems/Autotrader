"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2025-10-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Initial database schema for AutoTrader.
    
    Tables created:
    - scan_results: Token scan results from HiddenGemScanner
    - market_snapshots: Historical market data snapshots
    - narrative_insights: LLM-generated narrative analysis
    - safety_reports: Contract safety analysis results
    - agent_signals: BounceHunter agent signals (from agentic.py)
    - agent_fills: Trade fills (paper or live)
    - agent_outcomes: Trade outcomes with rewards
    - ticker_stats: Per-ticker performance statistics
    - system_state: System-wide key-value state
    """
    
    # Scan Results (HiddenGemScanner)
    op.create_table(
        'scan_results',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('token_symbol', sa.String(50), nullable=False, index=True),
        sa.Column('scan_timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('gem_score', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('flagged', sa.Boolean(), nullable=False, default=False),
        sa.Column('market_data', sa.JSON(), nullable=True),
        sa.Column('technical_metrics', sa.JSON(), nullable=True),
        sa.Column('sentiment_metrics', sa.JSON(), nullable=True),
        sa.Column('security_metrics', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    # Market Snapshots (time-series data)
    op.create_table(
        'market_snapshots',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('token_symbol', sa.String(50), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('price_usd', sa.Float(), nullable=True),
        sa.Column('volume_24h', sa.Float(), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('liquidity', sa.Float(), nullable=True),
        sa.Column('holder_count', sa.Integer(), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    # Narrative Insights (LLM analysis)
    op.create_table(
        'narrative_insights',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('token_symbol', sa.String(50), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('narrative_summary', sa.Text(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('llm_provider', sa.String(50), nullable=True),
        sa.Column('raw_response', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    # Safety Reports (contract analysis)
    op.create_table(
        'safety_reports',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column('contract_address', sa.String(100), nullable=False, index=True, unique=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=True),
        sa.Column('has_mint_function', sa.Boolean(), nullable=True),
        sa.Column('has_proxy', sa.Boolean(), nullable=True),
        sa.Column('owner_can_blacklist', sa.Boolean(), nullable=True),
        sa.Column('risk_flags', sa.JSON(), nullable=True),
        sa.Column('analysis_provider', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    # BounceHunter Agent System (from agentic.py)
    op.create_table(
        'agent_signals',
        sa.Column('signal_id', sa.String(100), nullable=False, primary_key=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('ticker', sa.String(20), nullable=False, index=True),
        sa.Column('date', sa.String(20), nullable=False),
        sa.Column('probability', sa.Float(), nullable=False),
        sa.Column('entry', sa.Float(), nullable=False),
        sa.Column('stop', sa.Float(), nullable=False),
        sa.Column('target', sa.Float(), nullable=False),
        sa.Column('regime', sa.String(50), nullable=False),
        sa.Column('size_pct', sa.Float(), nullable=False),
        sa.Column('z_score', sa.Float(), nullable=True),
        sa.Column('rsi2', sa.Float(), nullable=True),
        sa.Column('dist_200dma', sa.Float(), nullable=True),
        sa.Column('adv_usd', sa.Float(), nullable=True),
        sa.Column('sector', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('vetoed', sa.Boolean(), nullable=False, default=False),
        sa.Column('veto_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    op.create_table(
        'agent_fills',
        sa.Column('fill_id', sa.String(100), nullable=False, primary_key=True),
        sa.Column('signal_id', sa.String(100), nullable=False, index=True),
        sa.Column('ticker', sa.String(20), nullable=False, index=True),
        sa.Column('entry_date', sa.String(20), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('shares', sa.Float(), nullable=False),
        sa.Column('size_pct', sa.Float(), nullable=False),
        sa.Column('regime', sa.String(50), nullable=False),
        sa.Column('is_paper', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['signal_id'], ['agent_signals.signal_id']),
    )
    
    op.create_table(
        'agent_outcomes',
        sa.Column('outcome_id', sa.String(100), nullable=False, primary_key=True),
        sa.Column('fill_id', sa.String(100), nullable=False, index=True),
        sa.Column('ticker', sa.String(20), nullable=False, index=True),
        sa.Column('exit_date', sa.String(20), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=False),
        sa.Column('exit_reason', sa.String(50), nullable=False),
        sa.Column('hold_days', sa.Integer(), nullable=False),
        sa.Column('return_pct', sa.Float(), nullable=False),
        sa.Column('hit_target', sa.Boolean(), nullable=False, default=False),
        sa.Column('hit_stop', sa.Boolean(), nullable=False, default=False),
        sa.Column('hit_time', sa.Boolean(), nullable=False, default=False),
        sa.Column('reward', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['fill_id'], ['agent_fills.fill_id']),
    )
    
    op.create_table(
        'ticker_stats',
        sa.Column('ticker', sa.String(20), nullable=False, primary_key=True),
        sa.Column('last_updated', sa.DateTime(), nullable=False),
        sa.Column('total_signals', sa.Integer(), nullable=False, default=0),
        sa.Column('total_outcomes', sa.Integer(), nullable=False, default=0),
        sa.Column('base_rate', sa.Float(), nullable=False, default=0.0),
        sa.Column('avg_reward', sa.Float(), nullable=False, default=0.0),
        sa.Column('normal_regime_rate', sa.Float(), nullable=False, default=0.0),
        sa.Column('highvix_regime_rate', sa.Float(), nullable=False, default=0.0),
        sa.Column('ejected', sa.Boolean(), nullable=False, default=False),
        sa.Column('eject_reason', sa.Text(), nullable=True),
    )
    
    op.create_table(
        'system_state',
        sa.Column('key', sa.String(100), nullable=False, primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
    )
    
    # Create indexes for performance
    op.create_index('idx_scan_results_score', 'scan_results', ['gem_score'])
    op.create_index('idx_scan_results_flagged', 'scan_results', ['flagged'])
    op.create_index('idx_market_snapshots_symbol_timestamp', 'market_snapshots', ['token_symbol', 'timestamp'])
    op.create_index('idx_agent_signals_ticker_date', 'agent_signals', ['ticker', 'date'])
    op.create_index('idx_agent_outcomes_ticker', 'agent_outcomes', ['ticker'])


def downgrade() -> None:
    """Drop all tables"""
    op.drop_table('system_state')
    op.drop_table('ticker_stats')
    op.drop_table('agent_outcomes')
    op.drop_table('agent_fills')
    op.drop_table('agent_signals')
    op.drop_table('safety_reports')
    op.drop_table('narrative_insights')
    op.drop_table('market_snapshots')
    op.drop_table('scan_results')
