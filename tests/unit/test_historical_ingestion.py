import pandas as pd

from autotrader.backtesting.engine.historical import DuckDBHistoricalDatasetConnector
from autotrader.strategy.train import StrategyTrainer


def test_duckdb_connector_reads_mixed_schema_glob_without_quote_schema_failure(tmp_path):
    bar_df = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-05-18 10:00:00")],
            "symbol": ["EUR/USD"],
            "open": [1.0850],
            "high": [1.0855],
            "low": [1.0845],
            "close": [1.0852],
            "volume": [1000.0],
            "trades": [25],
        }
    )
    bar_df.to_parquet(tmp_path / "bars.parquet")

    tick_df = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-05-18 10:00:01")],
            "symbol": ["EUR/USD"],
            "bid": [1.0851],
            "ask": [1.0853],
            "bid_vol": [1_000_000.0],
            "ask_vol": [2_000_000.0],
        }
    )
    tick_df.to_parquet(tmp_path / "ticks.parquet")

    connector = DuckDBHistoricalDatasetConnector(
        dataset_glob=str(tmp_path / "*.parquet"),
        bid_size_col="bid_vol",
        ask_size_col="ask_vol",
    )

    quotes = list(connector.iter_quotes(symbol="EUR/USD"))

    assert len(quotes) == 1
    assert quotes[0].symbol == "EUR/USD"
    assert quotes[0].bid == 1.0851
    assert quotes[0].ask == 1.0853
    assert quotes[0].bid_size == 1_000_000.0
    assert quotes[0].ask_size == 2_000_000.0


def test_duckdb_connector_auto_detects_dukascopy_size_columns(tmp_path):
    tick_df = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-05-18 10:00:01")],
            "symbol": ["EUR/USD"],
            "bid": [1.0851],
            "ask": [1.0853],
            "bid_vol": [1_000_000.0],
            "ask_vol": [2_000_000.0],
        }
    )
    tick_df.to_parquet(tmp_path / "dukascopy_ticks.parquet")

    connector = DuckDBHistoricalDatasetConnector(dataset_glob=str(tmp_path / "*.parquet"))

    quotes = list(connector.iter_quotes(symbol="EUR/USD"))

    assert len(quotes) == 1
    assert quotes[0].bid_size == 1_000_000.0
    assert quotes[0].ask_size == 2_000_000.0


def test_strategy_trainer_normalizes_naive_execution_timestamps_against_utc_quotes():
    trainer = StrategyTrainer(dataset_glob="unused.parquet", symbol="EUR/USD")
    trainer._quotes_frame = pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2026-05-18 10:00:00", tz="UTC"),
                pd.Timestamp("2026-05-18 10:00:05", tz="UTC"),
            ],
            "mid": [1.0852, 1.0854],
        }
    )
    trainer.markout_ns = 1_000_000_000

    future_mid = trainer._future_mid_price(pd.Timestamp("2026-05-18 10:00:01"))

    assert future_mid == 1.0854