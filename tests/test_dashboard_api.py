from fastapi.testclient import TestClient

from src.services.dashboard_api import app


client = TestClient(app)


def test_list_tokens_returns_summaries() -> None:
    response = client.get("/api/tokens")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data, "expected at least one token summary"
    sample = data[0]
    assert "symbol" in sample
    assert "final_score" in sample
    assert "gem_score" in sample


def test_token_detail_contains_tree() -> None:
    tokens = client.get("/api/tokens").json()
    symbol = tokens[0]["symbol"]

    response = client.get(f"/api/tokens/{symbol}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["symbol"] == symbol
    assert "narrative" in payload
    assert "contributions" in payload
    assert "tree" in payload
    assert payload["tree"]["key"] == "root"
