"""
Label factory for unified access to all labeling methods.

Provides simple API for creating labels with classification or regression methods.
"""

from typing import Optional, Literal
import pandas as pd

from .base import CostModel, BaseLabeler
from .classification import ClassificationLabeler
from .regression import RegressionLabeler


class LabelFactory:
    """
    Factory for creating labels with unified API.
    
    Provides simple interface to generate cost-aware labels using
    either classification or regression methods.
    
    Example:
        >>> factory = LabelFactory()
        >>> labels = factory.create(
        ...     bars,
        ...     method="classification",
        ...     horizon_seconds=60
        ... )
    """
    
    @staticmethod
    def create(
        bars: pd.DataFrame,
        method: Literal["classification", "regression"] = "classification",
        horizon_seconds: int = 60,
        cost_model: Optional[CostModel] = None,
        price_col: str = "close",
        timestamp_col: str = "timestamp",
        bid_col: Optional[str] = "bid",
        ask_col: Optional[str] = "ask",
        bid_vol_col: Optional[str] = "bid_volume",
        ask_vol_col: Optional[str] = "ask_volume",
        is_maker: bool = True,
        use_microprice: bool = True,
        clip_percentiles: tuple = (5.0, 95.0),
        subtract_costs: bool = True,
    ) -> pd.DataFrame:
        """
        Generate labels using specified method.
        
        Args:
            bars: DataFrame with bar data
            method: "classification" or "regression"
            horizon_seconds: Forward-looking horizon
            cost_model: Transaction cost model (uses default if None)
            price_col: Price column name
            timestamp_col: Timestamp column name
            bid_col: Bid price column (for microprice)
            ask_col: Ask price column (for microprice)
            bid_vol_col: Bid volume column (for microprice)
            ask_vol_col: Ask volume column (for microprice)
            is_maker: Whether using maker fees (classification only)
            use_microprice: Whether to use microprice instead of close
            clip_percentiles: Percentile bounds for clipping (regression only)
            subtract_costs: Whether to subtract costs from labels (regression only)
            
        Returns:
            DataFrame with labels
            
        Raises:
            ValueError: If method is not recognized
        """
        # Create cost model if not provided
        if cost_model is None:
            cost_model = CostModel()
        
        # Create appropriate labeler
        if method == "classification":
            labeler = ClassificationLabeler(
                cost_model=cost_model,
                horizon_seconds=horizon_seconds,
                is_maker=is_maker,
                use_microprice=use_microprice,
            )
        elif method == "regression":
            labeler = RegressionLabeler(
                cost_model=cost_model,
                horizon_seconds=horizon_seconds,
                clip_percentiles=clip_percentiles,
                subtract_costs=subtract_costs,
                use_microprice=use_microprice,
            )
        else:
            raise ValueError(f"Unknown labeling method: {method}. Use 'classification' or 'regression'.")
        
        # Generate labels
        labeled_data = labeler.generate_labels(
            bars,
            price_col=price_col,
            timestamp_col=timestamp_col,
            bid_col=bid_col,
            ask_col=ask_col,
            bid_vol_col=bid_vol_col,
            ask_vol_col=ask_vol_col,
        )
        
        return labeled_data
    
    @staticmethod
    def get_labeler(
        method: Literal["classification", "regression"] = "classification",
        horizon_seconds: int = 60,
        cost_model: Optional[CostModel] = None,
        **kwargs
    ) -> BaseLabeler:
        """
        Get labeler instance without generating labels.
        
        Useful for accessing labeler methods like get_label_statistics().
        
        Args:
            method: "classification" or "regression"
            horizon_seconds: Forward-looking horizon
            cost_model: Transaction cost model
            **kwargs: Additional labeler-specific arguments
            
        Returns:
            Labeler instance
        """
        if cost_model is None:
            cost_model = CostModel()
        
        if method == "classification":
            return ClassificationLabeler(
                cost_model=cost_model,
                horizon_seconds=horizon_seconds,
                **kwargs
            )
        elif method == "regression":
            return RegressionLabeler(
                cost_model=cost_model,
                horizon_seconds=horizon_seconds,
                **kwargs
            )
        else:
            raise ValueError(f"Unknown labeling method: {method}")
    
    @staticmethod
    def get_statistics(
        labeled_data: pd.DataFrame,
        method: Literal["classification", "regression"] = "classification",
        cost_model: Optional[CostModel] = None,
        **kwargs
    ) -> dict:
        """
        Get statistics for already-generated labels.
        
        Args:
            labeled_data: DataFrame with labels (from create())
            method: Labeling method that was used
            cost_model: Cost model that was used
            **kwargs: Additional labeler arguments
            
        Returns:
            Statistics dictionary
        """
        labeler = LabelFactory.get_labeler(method=method, cost_model=cost_model, **kwargs)
        return labeler.get_label_statistics(labeled_data)
