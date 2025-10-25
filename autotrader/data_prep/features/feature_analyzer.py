"""
Feature analysis and importance ranking.

Analyzes feature quality, importance, and potential issues:
- Importance ranking (permutation, correlation)
- Performance metrics (IC, Sharpe)
- Leakage detection (forward correlation)
- Stability analysis (time decay)
- Correlation clustering
- Missing value analysis

Critical for feature engineering:
- Identify most predictive features
- Detect lookahead bias (leakage)
- Remove redundant features
- Monitor feature stability over time

References:
- Permutation importance: Breiman (2001)
- Information Coefficient: Fundamental Law of Active Management
- Leakage detection: Lopez de Prado (2018)
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Literal
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.inspection import permutation_importance
import matplotlib.pyplot as plt
import seaborn as sns


class FeatureAnalyzer:
    """
    Analyze feature importance, performance, and quality.
    
    Key analyses:
    1. Importance ranking (permutation, correlation with target)
    2. Information Coefficient (IC): feature-target correlation
    3. Leakage detection: forward-looking correlation check
    4. Stability: IC decay over time
    5. Redundancy: correlation clustering
    6. Missing values: completeness analysis
    
    Example:
        analyzer = FeatureAnalyzer()
        
        # Analyze features
        report = analyzer.analyze(
            features=features_df,
            target=returns,
            task='regression'
        )
        
        # Get top features
        top_features = report['importance'].nlargest(10)
        
        # Check for leakage
        leaky_features = report['leakage']
        
        # Plot importance
        analyzer.plot_importance(report)
    """
    
    def __init__(
        self,
        n_permutations: int = 10,
        random_state: int = 42
    ):
        """
        Initialize feature analyzer.
        
        Args:
            n_permutations: Number of permutations for importance
            random_state: Random seed for reproducibility
        """
        self.n_permutations = n_permutations
        self.random_state = random_state
    
    def analyze(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        task: Literal['regression', 'classification'] = 'regression',
        time_periods: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive feature analysis.
        
        Args:
            features: Feature DataFrame
            target: Target variable
            task: 'regression' or 'classification'
            time_periods: Number of periods for stability analysis
        
        Returns:
            Dictionary with analysis results:
            - importance: Feature importance scores
            - ic: Information Coefficient (correlation with target)
            - leakage: Potential leakage indicators
            - stability: IC stability over time
            - redundancy: Feature correlation matrix
            - missing: Missing value percentages
        """
        # Align features and target
        common_index = features.index.intersection(target.index)
        features_aligned = features.loc[common_index]
        target_aligned = target.loc[common_index]
        
        # Remove rows with NaN target
        valid_idx = target_aligned.notna()
        features_aligned = features_aligned[valid_idx]
        target_aligned = target_aligned[valid_idx]
        
        report = {}
        
        # 1. Permutation importance
        report['importance'] = self._calculate_permutation_importance(
            features_aligned, target_aligned, task
        )
        
        # 2. Information Coefficient (IC)
        report['ic'] = self._calculate_ic(features_aligned, target_aligned)
        
        # 3. Leakage detection
        report['leakage'] = self._detect_leakage(features_aligned, target_aligned)
        
        # 4. Stability analysis (if time_periods specified)
        if time_periods is not None and time_periods > 1:
            report['stability'] = self._analyze_stability(
                features_aligned, target_aligned, time_periods
            )
        
        # 5. Redundancy analysis
        report['redundancy'] = self._analyze_redundancy(features_aligned)
        
        # 6. Missing value analysis
        report['missing'] = self._analyze_missing(features)
        
        return report
    
    def _calculate_permutation_importance(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        task: str
    ) -> pd.Series:
        """
        Calculate permutation importance using Random Forest.
        
        Permutation importance:
        - Shuffle each feature
        - Measure decrease in model performance
        - Higher decrease = more important feature
        
        Reference: Breiman (2001) "Random Forests"
        """
        # Remove features with all NaN or constant
        valid_features = features.dropna(axis=1, how='all')
        valid_features = valid_features.loc[:, valid_features.nunique() > 1]
        
        if len(valid_features.columns) == 0:
            return pd.Series(dtype=float)
        
        # Fill remaining NaN with median
        valid_features = valid_features.fillna(valid_features.median())
        
        # Build model
        if task == 'regression':
            model = RandomForestRegressor(
                n_estimators=50,
                max_depth=5,
                random_state=self.random_state,
                n_jobs=-1
            )
        else:
            model = RandomForestClassifier(
                n_estimators=50,
                max_depth=5,
                random_state=self.random_state,
                n_jobs=-1
            )
        
        # Fit model
        model.fit(valid_features, target)
        
        # Calculate permutation importance
        perm_importance = permutation_importance(
            model,
            valid_features,
            target,
            n_repeats=self.n_permutations,
            random_state=self.random_state,
            n_jobs=-1
        )
        
        # Create series
        importance_series = pd.Series(
            perm_importance.importances_mean,
            index=valid_features.columns
        ).sort_values(ascending=False)
        
        return importance_series
    
    def _calculate_ic(
        self,
        features: pd.DataFrame,
        target: pd.Series
    ) -> pd.Series:
        """
        Calculate Information Coefficient (IC).
        
        IC = correlation(feature, target)
        
        Measures linear predictive power of each feature.
        High |IC| = strong predictive power.
        
        Reference: Fundamental Law of Active Management
        """
        ic_scores = {}
        
        for col in features.columns:
            feature_series = features[col].dropna()
            target_aligned = target.reindex(feature_series.index)
            
            # Remove NaN in target
            valid_idx = target_aligned.notna()
            feature_series = feature_series[valid_idx]
            target_aligned = target_aligned[valid_idx]
            
            if len(feature_series) > 1:
                ic = feature_series.corr(target_aligned)
                ic_scores[col] = ic if not np.isnan(ic) else 0
            else:
                ic_scores[col] = 0
        
        ic_series = pd.Series(ic_scores).sort_values(
            key=abs, ascending=False
        )
        
        return ic_series
    
    def _detect_leakage(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        threshold: float = 0.1
    ) -> Dict[str, float]:
        """
        Detect potential lookahead bias (leakage).
        
        Method: Check correlation of features at time t with target at t-1
        (backward correlation). High backward correlation suggests leakage.
        
        Leakage = features using future information.
        
        Reference: Lopez de Prado (2018) Chapter 7
        """
        # Shift target backward (features at t, target at t-1)
        target_backward = target.shift(-1)
        
        leaky_features = {}
        
        for col in features.columns:
            feature_series = features[col].dropna()
            target_aligned = target_backward.reindex(feature_series.index)
            
            # Remove NaN in target
            valid_idx = target_aligned.notna()
            feature_series = feature_series[valid_idx]
            target_aligned = target_aligned[valid_idx]
            
            if len(feature_series) > 1:
                backward_corr = feature_series.corr(target_aligned)
                
                # Check if backward correlation is suspiciously high
                if abs(backward_corr) > threshold and not np.isnan(backward_corr):
                    leaky_features[col] = backward_corr
        
        return leaky_features
    
    def _analyze_stability(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        time_periods: int
    ) -> pd.DataFrame:
        """
        Analyze IC stability over time.
        
        Splits data into time periods and calculates IC for each.
        Stable features maintain consistent IC across periods.
        
        Returns DataFrame with IC per period for each feature.
        """
        # Split into time periods
        period_size = len(features) // time_periods
        
        stability_results = []
        
        for period in range(time_periods):
            start_idx = period * period_size
            end_idx = start_idx + period_size if period < time_periods - 1 else len(features)
            
            features_period = features.iloc[start_idx:end_idx]
            target_period = target.iloc[start_idx:end_idx]
            
            # Calculate IC for this period
            ic_period = self._calculate_ic(features_period, target_period)
            
            stability_results.append(ic_period)
        
        # Combine into DataFrame
        stability_df = pd.DataFrame(stability_results).T
        stability_df.columns = [f'period_{i+1}' for i in range(time_periods)]
        
        # Add mean and std
        stability_df['mean_ic'] = stability_df.mean(axis=1)
        stability_df['std_ic'] = stability_df.std(axis=1)
        stability_df['stability_ratio'] = (
            abs(stability_df['mean_ic']) / (stability_df['std_ic'] + 1e-6)
        )
        
        return stability_df.sort_values('stability_ratio', ascending=False)
    
    def _analyze_redundancy(
        self,
        features: pd.DataFrame,
        correlation_threshold: float = 0.9
    ) -> Dict[str, Any]:
        """
        Analyze feature redundancy (high correlation).
        
        Finds groups of highly correlated features.
        Redundant features can be removed to reduce overfitting.
        
        Returns:
        - correlation_matrix: Full correlation matrix
        - redundant_pairs: Pairs with correlation > threshold
        """
        # Calculate correlation matrix
        corr_matrix = features.corr()
        
        # Find redundant pairs
        redundant_pairs = []
        
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                col1 = corr_matrix.columns[i]
                col2 = corr_matrix.columns[j]
                corr_val = corr_matrix.iloc[i, j]
                
                if abs(corr_val) > correlation_threshold and not np.isnan(corr_val):
                    redundant_pairs.append({
                        'feature1': col1,
                        'feature2': col2,
                        'correlation': corr_val
                    })
        
        return {
            'correlation_matrix': corr_matrix,
            'redundant_pairs': redundant_pairs
        }
    
    def _analyze_missing(self, features: pd.DataFrame) -> pd.Series:
        """
        Analyze missing values in features.
        
        Returns percentage of missing values per feature.
        """
        missing_pct = (features.isna().sum() / len(features)) * 100
        missing_pct = missing_pct.sort_values(ascending=False)
        
        return missing_pct
    
    def plot_importance(
        self,
        report: Dict[str, Any],
        top_n: int = 20,
        figsize: tuple = (12, 8)
    ):
        """
        Plot feature importance.
        
        Args:
            report: Analysis report from analyze()
            top_n: Number of top features to show
            figsize: Figure size
        """
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        
        # 1. Permutation importance
        importance = report['importance'].head(top_n)
        axes[0, 0].barh(range(len(importance)), importance.values)
        axes[0, 0].set_yticks(range(len(importance)))
        axes[0, 0].set_yticklabels(importance.index)
        axes[0, 0].set_xlabel('Permutation Importance')
        axes[0, 0].set_title('Top Features by Permutation Importance')
        axes[0, 0].invert_yaxis()
        
        # 2. Information Coefficient (IC)
        ic = report['ic'].head(top_n)
        axes[0, 1].barh(range(len(ic)), ic.values)
        axes[0, 1].set_yticks(range(len(ic)))
        axes[0, 1].set_yticklabels(ic.index)
        axes[0, 1].set_xlabel('IC (Correlation with Target)')
        axes[0, 1].set_title('Top Features by IC')
        axes[0, 1].invert_yaxis()
        
        # 3. Missing values
        missing = report['missing'].head(top_n)
        axes[1, 0].barh(range(len(missing)), missing.values)
        axes[1, 0].set_yticks(range(len(missing)))
        axes[1, 0].set_yticklabels(missing.index)
        axes[1, 0].set_xlabel('Missing %')
        axes[1, 0].set_title('Features with Most Missing Values')
        axes[1, 0].invert_yaxis()
        
        # 4. Correlation heatmap (top features)
        top_features = importance.index[:10]
        corr_matrix = report['redundancy']['correlation_matrix'].loc[
            top_features, top_features
        ]
        sns.heatmap(
            corr_matrix,
            annot=True,
            fmt='.2f',
            cmap='coolwarm',
            center=0,
            ax=axes[1, 1]
        )
        axes[1, 1].set_title('Feature Correlation (Top 10)')
        
        plt.tight_layout()
        return fig
    
    def generate_report(
        self,
        report: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate text report of feature analysis.
        
        Args:
            report: Analysis report from analyze()
            output_path: Path to save report (None = return string)
        
        Returns:
            Report as string
        """
        lines = []
        lines.append("=" * 80)
        lines.append("FEATURE ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # 1. Top features by importance
        lines.append("TOP 10 FEATURES BY PERMUTATION IMPORTANCE:")
        lines.append("-" * 80)
        for i, (feat, score) in enumerate(report['importance'].head(10).items(), 1):
            lines.append(f"  {i:2d}. {feat:40s}  {score:.6f}")
        lines.append("")
        
        # 2. Top features by IC
        lines.append("TOP 10 FEATURES BY INFORMATION COEFFICIENT:")
        lines.append("-" * 80)
        for i, (feat, ic) in enumerate(report['ic'].head(10).items(), 1):
            lines.append(f"  {i:2d}. {feat:40s}  {ic:+.6f}")
        lines.append("")
        
        # 3. Potential leakage
        if report['leakage']:
            lines.append("⚠️  POTENTIAL LOOKAHEAD BIAS DETECTED:")
            lines.append("-" * 80)
            for feat, backward_corr in report['leakage'].items():
                lines.append(f"  {feat:40s}  backward_corr={backward_corr:+.6f}")
            lines.append("")
        else:
            lines.append("✓ NO LOOKAHEAD BIAS DETECTED")
            lines.append("")
        
        # 4. Redundant features
        redundant_pairs = report['redundancy']['redundant_pairs']
        if redundant_pairs:
            lines.append(f"REDUNDANT FEATURE PAIRS ({len(redundant_pairs)} found):")
            lines.append("-" * 80)
            for pair in redundant_pairs[:10]:  # Show top 10
                lines.append(
                    f"  {pair['feature1']:30s} <-> {pair['feature2']:30s}  "
                    f"corr={pair['correlation']:+.6f}"
                )
            lines.append("")
        
        # 5. Missing values
        missing_features = report['missing'][report['missing'] > 0]
        if len(missing_features) > 0:
            lines.append(f"FEATURES WITH MISSING VALUES ({len(missing_features)} features):")
            lines.append("-" * 80)
            for feat, pct in missing_features.head(10).items():
                lines.append(f"  {feat:40s}  {pct:5.2f}%")
            lines.append("")
        
        # 6. Stability (if available)
        if 'stability' in report:
            lines.append("FEATURE STABILITY (IC consistency over time):")
            lines.append("-" * 80)
            stability = report['stability'].head(10)
            for feat in stability.index:
                mean_ic = stability.loc[feat, 'mean_ic']
                std_ic = stability.loc[feat, 'std_ic']
                stability_ratio = stability.loc[feat, 'stability_ratio']
                lines.append(
                    f"  {feat:40s}  mean_IC={mean_ic:+.4f}  "
                    f"std_IC={std_ic:.4f}  stability={stability_ratio:.2f}"
                )
            lines.append("")
        
        lines.append("=" * 80)
        
        report_text = "\n".join(lines)
        
        # Save to file if requested
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report_text)
        
        return report_text
