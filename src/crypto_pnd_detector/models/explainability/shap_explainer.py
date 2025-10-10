"""Rule-based explainer that mimics SHAP style outputs."""

from __future__ import annotations

from typing import Dict, List, Tuple


class SimpleFeatureExplainer:
    """Produces contribution style explanations by ranking absolute values."""

    def explain(self, features: Dict[str, float], *, top_k: int = 5) -> List[Tuple[str, float]]:
        ranked = sorted(features.items(), key=lambda item: abs(item[1]), reverse=True)
        return ranked[:top_k]
