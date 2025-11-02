"""
Robust normalization utilities for feature engineering.

Provides safe z-score normalization and winsorization to prevent
NaN/inf propagation in ML pipelines.
"""

import numpy as np


def safe_zscore(x, axis=0, eps=1e-8):
    """
    Z-score normalization with NaN/inf protection.
    
    Args:
        x: Input array
        axis: Axis along which to compute statistics
        eps: Minimum standard deviation to prevent division by zero
    
    Returns:
        Normalized array with no NaNs or infs
    """
    mu = np.nanmean(x, axis=axis, keepdims=True)
    sd = np.nanstd(x, axis=axis, keepdims=True)
    sd = np.where(sd < eps, eps, sd)
    z = (x - mu) / sd
    return np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)


def winsorize(x, p=0.005):
    """
    Winsorize outliers to percentile bounds.
    
    Args:
        x: Input array
        p: Percentile to clip (e.g., 0.005 = 0.5% and 99.5%)
    
    Returns:
        Clipped array with tails constrained
    """
    lo, hi = np.nanquantile(x, [p, 1 - p], axis=0)
    return np.clip(x, lo, hi)
