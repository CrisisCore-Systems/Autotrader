"""
Feature selection and correlation analysis.

Provides tools to:
- Detect redundant features (high correlation)
- Reduce feature set intelligently
- Analyze correlation structure
- Optional PCA compression

Redundant features can:
- Slow down training
- Increase overfitting risk
- Waste computation
- Confuse feature importance

Example redundancies in our features:
- log_return vs simple_return (nearly identical for small returns)
- Multiple highly correlated window sizes
- MACD line/signal/histogram (linearly dependent)
"""

import pandas as pd
import numpy as np
from typing import Optional, Literal
from sklearn.decomposition import PCA


class FeatureSelector:
    """
    Intelligent feature selection and correlation analysis.
    
    Helps identify and remove redundant features while preserving
    information content.
    
    Example:
        selector = FeatureSelector(correlation_threshold=0.9)
        
        # Analyze correlations
        analysis = selector.analyze_correlation(features)
        print(f"Found {len(analysis['high_correlation_pairs'])} redundant pairs")
        
        # Remove redundant features
        reduced = selector.reduce_features(features, method="correlation")
        print(f"Reduced from {len(features.columns)} to {len(reduced.columns)} features")
        
        # Or use PCA
        compressed = selector.reduce_features(features, method="pca", n_components=20)
    """
    
    def __init__(
        self,
        correlation_threshold: float = 0.9,
        min_importance_ratio: float = 0.01
    ):
        """
        Initialize feature selector.
        
        Args:
            correlation_threshold: Correlation above this is considered redundant
            min_importance_ratio: Features below this importance ratio are candidates for removal
        """
        self.correlation_threshold = correlation_threshold
        self.min_importance_ratio = min_importance_ratio
        self._correlation_matrix = None
    
    def analyze_correlation(self, features: pd.DataFrame) -> dict:
        """
        Analyze correlation structure of features.
        
        Args:
            features: Feature DataFrame
        
        Returns:
            Dictionary with correlation analysis:
            - correlation_matrix: Full correlation matrix
            - high_correlation_pairs: List of (feature1, feature2, correlation)
            - feature_clusters: Groups of highly correlated features
        """
        # Calculate correlation matrix
        self._correlation_matrix = features.corr()
        
        # Find high correlation pairs
        high_corr_pairs = []
        n_features = len(features.columns)
        
        for i in range(n_features):
            for j in range(i + 1, n_features):  # Upper triangle only
                corr = abs(self._correlation_matrix.iloc[i, j])
                if corr >= self.correlation_threshold:
                    high_corr_pairs.append((
                        features.columns[i],
                        features.columns[j],
                        corr
                    ))
        
        # Sort by correlation (highest first)
        high_corr_pairs.sort(key=lambda x: x[2], reverse=True)
        
        # Find clusters of correlated features
        clusters = self._find_correlation_clusters(features)
        
        return {
            "correlation_matrix": self._correlation_matrix,
            "high_correlation_pairs": high_corr_pairs,
            "feature_clusters": clusters,
            "summary": {
                "total_features": n_features,
                "redundant_pairs": len(high_corr_pairs),
                "num_clusters": len(clusters)
            }
        }
    
    def _find_correlation_clusters(self, features: pd.DataFrame) -> list[list[str]]:
        """
        Find clusters of mutually correlated features.
        
        Uses simple greedy clustering: features are in same cluster if
        they're all highly correlated with each other.
        
        Args:
            features: Feature DataFrame
        
        Returns:
            List of feature clusters (each cluster is list of feature names)
        """
        if self._correlation_matrix is None:
            self._correlation_matrix = features.corr()
        
        clusters = []
        assigned = set()
        
        for col in features.columns:
            if col in assigned:
                continue
            
            # Find all features highly correlated with this one
            cluster = [col]
            correlated = []
            
            for other_col in features.columns:
                if other_col == col or other_col in assigned:
                    continue
                
                corr = abs(self._correlation_matrix.loc[col, other_col])
                if corr >= self.correlation_threshold:
                    correlated.append(other_col)
            
            # Add to cluster if mutually correlated
            cluster.extend(correlated)
            
            if len(cluster) > 1:
                clusters.append(cluster)
                assigned.update(cluster)
        
        return clusters
    
    def reduce_features(
        self,
        features: pd.DataFrame,
        method: Literal["correlation", "pca"] = "correlation",
        feature_importance: Optional[dict[str, float]] = None,
        n_components: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Reduce feature set by removing redundancy.
        
        Args:
            features: Feature DataFrame
            method: Reduction method
                'correlation': Remove one feature from each correlated pair
                'pca': Use PCA to compress features
            feature_importance: Optional importance scores to guide selection
            n_components: For PCA, number of components (None = auto)
        
        Returns:
            Reduced feature DataFrame
        """
        if method == "correlation":
            return self._reduce_by_correlation(features, feature_importance)
        elif method == "pca":
            return self._reduce_by_pca(features, n_components)
        else:
            raise ValueError(f"Unknown reduction method: {method}")
    
    def _reduce_by_correlation(
        self,
        features: pd.DataFrame,
        feature_importance: Optional[dict[str, float]] = None
    ) -> pd.DataFrame:
        """
        Remove features based on correlation.
        
        For each correlated pair, keep the more important feature
        (or the first one if no importance scores).
        """
        if self._correlation_matrix is None:
            self._correlation_matrix = features.corr()
        
        # Track features to remove
        to_remove = set()
        
        # Process each pair of highly correlated features
        n_features = len(features.columns)
        for i in range(n_features):
            for j in range(i + 1, n_features):
                feat1 = features.columns[i]
                feat2 = features.columns[j]
                
                # Skip if already marked for removal
                if feat1 in to_remove or feat2 in to_remove:
                    continue
                
                corr = abs(self._correlation_matrix.iloc[i, j])
                if corr >= self.correlation_threshold:
                    # Decide which to keep
                    if feature_importance is not None:
                        imp1 = feature_importance.get(feat1, 0)
                        imp2 = feature_importance.get(feat2, 0)
                        
                        # Remove less important feature
                        if imp1 < imp2:
                            to_remove.add(feat1)
                        else:
                            to_remove.add(feat2)
                    else:
                        # No importance scores, remove second feature
                        to_remove.add(feat2)
        
        # Return features not marked for removal
        keep_features = [col for col in features.columns if col not in to_remove]
        return features[keep_features]
    
    def _reduce_by_pca(
        self,
        features: pd.DataFrame,
        n_components: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Reduce features using PCA.
        
        Args:
            features: Feature DataFrame
            n_components: Number of components (None = explain 95% variance)
        
        Returns:
            PCA-transformed features
        """
        # Determine number of components
        if n_components is None:
            # Auto: keep 95% of variance
            pca = PCA(n_components=0.95)
        else:
            pca = PCA(n_components=n_components)
        
        # Fit and transform
        transformed = pca.fit_transform(features)
        
        # Create DataFrame with PC names
        pc_names = [f"PC{i+1}" for i in range(transformed.shape[1])]
        
        return pd.DataFrame(
            transformed,
            index=features.index,
            columns=pc_names
        )
    
    def get_redundancy_report(self, features: pd.DataFrame) -> dict:
        """
        Get detailed report on feature redundancy.
        
        Args:
            features: Feature DataFrame
        
        Returns:
            Dictionary with redundancy analysis
        """
        analysis = self.analyze_correlation(features)
        
        # Identify most redundant features
        redundancy_count = {}
        for feat1, feat2, corr in analysis["high_correlation_pairs"]:
            redundancy_count[feat1] = redundancy_count.get(feat1, 0) + 1
            redundancy_count[feat2] = redundancy_count.get(feat2, 0) + 1
        
        most_redundant = sorted(
            redundancy_count.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]  # Top 10
        
        return {
            "total_features": len(features.columns),
            "redundant_pairs": len(analysis["high_correlation_pairs"]),
            "clusters": analysis["feature_clusters"],
            "most_redundant_features": most_redundant,
            "estimated_removable": len(analysis["high_correlation_pairs"]),
            "compression_potential": {
                "current": len(features.columns),
                "after_correlation_filter": len(features.columns) - len(analysis["high_correlation_pairs"]),
                "pca_95_variance": self._estimate_pca_components(features, 0.95)
            }
        }
    
    def _estimate_pca_components(self, features: pd.DataFrame, variance_ratio: float) -> int:
        """Estimate number of PCA components needed for variance ratio."""
        pca = PCA(n_components=variance_ratio)
        pca.fit(features)
        return pca.n_components_
    
    def visualize_correlation(
        self,
        features: pd.DataFrame,
        method: Literal["heatmap", "network"] = "heatmap"
    ) -> str:
        """
        Generate correlation visualization.
        
        Args:
            features: Feature DataFrame
            method: Visualization type
                'heatmap': Correlation matrix heatmap
                'network': Network graph of correlations
        
        Returns:
            String describing visualization (actual plotting requires matplotlib)
        """
        if self._correlation_matrix is None:
            self._correlation_matrix = features.corr()
        
        if method == "heatmap":
            return self._describe_heatmap()
        elif method == "network":
            return self._describe_network()
        else:
            raise ValueError(f"Unknown visualization method: {method}")
    
    def _describe_heatmap(self) -> str:
        """Describe how to create correlation heatmap."""
        return """
To create correlation heatmap:

import matplotlib.pyplot as plt
import seaborn as sns

plt.figure(figsize=(12, 10))
sns.heatmap(
    correlation_matrix,
    cmap='coolwarm',
    center=0,
    vmin=-1,
    vmax=1,
    square=True,
    cbar_kws={'label': 'Correlation'}
)
plt.title('Feature Correlation Matrix')
plt.tight_layout()
plt.show()
"""
    
    def _describe_network(self) -> str:
        """Describe how to create correlation network."""
        return """
To create correlation network:

import networkx as nx
import matplotlib.pyplot as plt

# Create graph
G = nx.Graph()

# Add edges for high correlations
for feat1, feat2, corr in high_correlation_pairs:
    G.add_edge(feat1, feat2, weight=corr)

# Draw network
pos = nx.spring_layout(G)
nx.draw_networkx_nodes(G, pos, node_size=500, node_color='lightblue')
nx.draw_networkx_labels(G, pos, font_size=8)
nx.draw_networkx_edges(G, pos, width=2, alpha=0.5)

plt.title('Feature Correlation Network (≥0.9)')
plt.axis('off')
plt.tight_layout()
plt.show()
"""
