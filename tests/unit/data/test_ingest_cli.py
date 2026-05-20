import asyncio
from datetime import datetime, timedelta

import httpx
import pandas as pd

from autotrader.data import ingest
from orchestration.flows import ingest_dukascopy


def test_ingest_dukascopy_range_writes_to_requested_output_dir(tmp_path, monkeypatch):
    async def _fake_fetch_bi5_file(instrument, year, month, day, hour):
        return b"fake"

    monkeypatch.setattr(ingest_dukascopy, "fetch_bi5_file", _fake_fetch_bi5_file)
    monkeypatch.setattr(
        ingest_dukascopy,
        "decompress_bi5_payload",
        lambda data: [(0, 1.0851, 1.0853, 1_000_000.0, 2_000_000.0)],
    )

    start_time = datetime(2024, 10, 21, 10, 0, 0)
    written_files = asyncio.run(
        ingest_dukascopy.ingest_dukascopy_range(
            instruments=["EUR/USD"],
            start_time=start_time,
            end_time=start_time + timedelta(hours=1),
            output_dir=tmp_path,
        )
    )

    assert len(written_files) == 1
    output_path = written_files[0]
    assert output_path.exists()

    df = pd.read_parquet(output_path)
    assert df.loc[0, "symbol"] == "EUR/USD"
    assert df.loc[0, "bid_vol"] == 1_000_000.0
    assert df.loc[0, "ask_vol"] == 2_000_000.0


def test_cli_main_passes_requested_dates_and_output_dir(tmp_path, monkeypatch, capsys):
    captured = {}

    async def _fake_ingest_dukascopy_range(instruments, start_time, end_time, output_dir):
        captured["instruments"] = instruments
        captured["start_time"] = start_time
        captured["end_time"] = end_time
        captured["output_dir"] = output_dir
        output_path = tmp_path / "EURUSD_20241021_00.parquet"
        output_path.write_bytes(b"ok")
        return [output_path]

    monkeypatch.setattr(ingest, "ingest_dukascopy_range", _fake_ingest_dukascopy_range)

    exit_code = ingest.main(
        [
            "--symbol",
            "EUR/USD",
            "--start-date",
            "2024-10-21",
            "--end-date",
            "2024-10-22",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert captured["instruments"] == ["EUR/USD"]
    assert captured["start_time"] == datetime(2024, 10, 21, 0, 0, 0)
    assert captured["end_time"] == datetime(2024, 10, 22, 0, 0, 0)
    assert captured["output_dir"] == tmp_path

    stdout = capsys.readouterr().out
    assert "Wrote 1 parquet file(s)" in stdout


def test_fetch_bi5_file_retries_transient_503(monkeypatch):
    attempts = {"count": 0}

    class _FakeResponse:
        def __init__(self, status_code, content=b"ok"):
            self.status_code = status_code
            self.content = content
            self.request = httpx.Request("GET", "https://datafeed.dukascopy.com")

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"status {self.status_code}",
                    request=self.request,
                    response=self,
                )

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, timeout):
            attempts["count"] += 1
            if attempts["count"] == 1:
                return _FakeResponse(503)
            return _FakeResponse(200, content=b"payload")

    async def _fake_sleep(seconds):
        return None

    monkeypatch.setattr(ingest_dukascopy.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(ingest_dukascopy.asyncio, "sleep", _fake_sleep)

    payload = asyncio.run(ingest_dukascopy.fetch_bi5_file("EUR/USD", 2024, 9, 20, 0))

    assert payload == b"payload"
    assert attempts["count"] == 2