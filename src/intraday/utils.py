"""
Utility functions for intraday feature engineering.

Provides robust normalization and data validation helpers
to prevent NaN propagation in reinforcement learning pipelines.
"""

import numpy as np
from typing import Optional, Tuple


def drop_constant_cols(
    X: np.ndarray,
    eps: float = 1e-12
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Remove constant columns from feature matrix.
    
    Prevents divide-by-zero in correlation and z-score computations.
    
    Args:
        X: Input array (n_samples, n_features)
        eps: Minimum standard deviation threshold
    
    Returns:
        (filtered_array, keep_mask) where keep_mask indicates retained columns
    
    Example:
        >>> X_clean, keep = drop_constant_cols(X)
        >>> assert X_clean.shape[1] <= X.shape[1]
    """
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    
    sd = np.nanstd(X, axis=0)
    keep = sd > eps
    
    if not np.any(keep):
        # All columns constant - return single zero column
        return np.zeros((X.shape[0], 1), dtype=X.dtype), np.array([False])
    
    return X[:, keep], keep


def safe_zscore(
    x: np.ndarray,
    axis: int = 0,
    eps: float = 1e-8
) -> np.ndarray:
    """
    Compute z-score normalization with NaN protection.
    
    Prevents division by zero and clamps output to finite values.
    
    Args:
        x: Input array
        axis: Axis along which to normalize
        eps: Minimum standard deviation threshold
    
    Returns:
        Z-score normalized array with no NaNs/Infs
    
    Example:
        >>> features = safe_zscore(raw_features, axis=0)
        >>> assert np.isfinite(features).all()
    """
    mu = np.nanmean(x, axis=axis, keepdims=True)
    sd = np.nanstd(x, axis=axis, keepdims=True)
    sd = np.maximum(sd, eps)  # More robust than np.where
    z = (x - mu) / sd
    return np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)


def safe_corrcoef(
    X: np.ndarray,
    eps: float = 1e-8
) -> np.ndarray:
    """
    Compute correlation matrix with NaN protection.
    
    Removes constant columns and ensures finite output.
    
    Args:
        X: Input array (n_samples, n_features)
        eps: Minimum standard deviation threshold
    
    Returns:
        Correlation matrix (n_features, n_features) with no NaNs/Infs
    
    Example:
        >>> corr = safe_corrcoef(features)
        >>> assert np.isfinite(corr).all()
        >>> assert np.allclose(corr, corr.T)  # symmetric
    """
    X, keep = drop_constant_cols(X, eps)
    
    if X.size == 0 or X.shape[1] == 0:
        return np.zeros((1, 1), dtype=float)
    
    # Standardize then compute correlation via Z^T @ Z / (n-1)
    Z = safe_zscore(X, axis=0, eps=eps)
    n = Z.shape[0]
    C = (Z.T @ Z) / max(n - 1, 1)
    C = np.clip(C, -1.0, 1.0)
    
    return np.nan_to_num(C, nan=0.0, posinf=0.0, neginf=0.0)


def winsorize(
    x: np.ndarray,
    p: float = 0.005,
    axis: int = 0
) -> np.ndarray:
    """
    Winsorize outliers to specified quantile bounds.
    
    Clips extreme values to prevent feature explosion in
    extended microstructure metrics (order flow, tail stats).
    
    Args:
        x: Input array
        p: Quantile threshold (e.g., 0.005 = clip to 0.5th/99.5th percentile)
        axis: Axis along which to compute quantiles
    
    Returns:
        Winsorized array
    
    Example:
        >>> features = winsorize(features, p=0.005)
        >>> features = safe_zscore(features)
    """
    lo, hi = np.nanquantile(x, [p, 1 - p], axis=axis, keepdims=True)
    return np.clip(x, lo, hi)


def validate_features(
    features: np.ndarray,
    name: str = "features",
    warn: bool = True
) -> np.ndarray:
    """
    Validate feature array and replace invalid values.
    
    Args:
        features: Feature array to validate
        name: Name for logging
        warn: Whether to log warnings
    
    Returns:
        Validated feature array with NaNs/Infs replaced by 0
    """
    if not np.isfinite(features).all():
        if warn:
            import logging
            logger = logging.getLogger(__name__)
            nan_count = np.isnan(features).sum()
            inf_count = np.isinf(features).sum()
            logger.warning(
                f"{name}: replacing {nan_count} NaNs and {inf_count} Infs with 0"
            )
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
    return features


def assert_finite(name: str, arr: np.ndarray) -> None:
    """
    Assert array contains only finite values.
    
    Raises:
        ValueError: If array contains NaN or Inf
    
    Example:
        >>> assert_finite("observation", obs)
    """
    if not np.isfinite(arr).all():
        bad = np.where(~np.isfinite(arr))
        nan_count = np.isnan(arr).sum()
        inf_count = np.isinf(arr).sum()
        raise ValueError(
            f"{name}: contains {nan_count} NaNs and {inf_count} Infs at indices {bad}"
        )


def check_warmup(
    bars: list,
    min_bars: int = 200,
    name: str = "data"
) -> None:
    """
    Ensure sufficient warmup period for indicators.
    
    Raises:
        ValueError: If insufficient bars for warmup
    
    Example:
        >>> bars = pipeline.get_latest_bars(500)
        >>> check_warmup(bars, min_bars=200)
    """
    if len(bars) < min_bars:
        raise ValueError(
            f"{name}: insufficient warmup data "
            f"(got {len(bars)} bars, need {min_bars})"
        )
