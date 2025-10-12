import json

notebook_data = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# VoidBloom / CrisisCore Prototype Notebook\n",
                "This notebook demonstrates a minimal ingest -> feature -> GemScore flow using synthetic data."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import pandas as pd\n",
                "from datetime import datetime, timedelta\n",
                "from src.core.features import MarketSnapshot, compute_time_series_features, build_feature_vector\n",
                "from src.core.safety import evaluate_contract, liquidity_guardrail, apply_penalties\n",
                "from src.core.scoring import compute_gem_score, should_flag_asset\n",
                "\n",
                "now = datetime.utcnow()\n",
                "dates = [now - timedelta(hours=i) for i in range(48)][::-1]\n",
                "prices = pd.Series(\n",
                "    data=[0.03 + 0.0002 * i for i in range(48)],\n",
                "    index=pd.to_datetime(dates)\n",
                ")"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "price_features = compute_time_series_features(prices)\n",
                "snapshot = MarketSnapshot(\n",
                "    symbol=\"VBLOOM\",\n",
                "    timestamp=now,\n",
                "    price=float(prices.iloc[-1]),\n",
                "    volume_24h=250000,\n",
                "    liquidity_usd=180000,\n",
                "    holders=4200,\n",
                "    onchain_metrics={\"active_wallets\": 950, \"net_inflows\": 125000, \"unlock_pressure\": 0.2},\n",
                "    narratives=[\"AI\", \"DeFi\", \"VoidBloom\"]\n",
                ")\n",
                "contract_report = evaluate_contract(\n",
                "    {\"honeypot\": False, \"owner_can_mint\": False, \"owner_can_withdraw\": False, \"unverified\": False},\n",
                "    severity=\"none\"\n",
                ")\n",
                "base_vector = build_feature_vector(\n",
                "    snapshot,\n",
                "    price_features,\n",
                "    narrative_embedding_score=0.72,\n",
                "    contract_safety={\"score\": contract_report.score, \"narrative_momentum\": 0.66}\n",
                ")\n",
                "features = apply_penalties(\n",
                "    base_vector,\n",
                "    contract_report,\n",
                "    liquidity_ok=liquidity_guardrail(snapshot.liquidity_usd)\n",
                ")\n",
                "features.update({\"Recency\": 0.9, \"DataCompleteness\": 0.85})\n",
                "features"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "result = compute_gem_score(features)\n",
                "flagged, debug = should_flag_asset(result, features)\n",
                "result, flagged, debug"
            ]
        }
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.11.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

with open("notebooks/hidden_gem_scanner.ipynb", "w") as f:
    json.dump(notebook_data, f, indent=2)

print("✓ Notebook created successfully")
