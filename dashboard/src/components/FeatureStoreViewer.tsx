/**
 * Feature Store Viewer Component
 * Browse and display feature store data for tokens
 */

import React, { useState, useEffect } from 'react';
import { fetchFeatures, fetchFeatureSchema } from '../api';
import { FeatureValue } from '../types';

interface FeatureStoreViewerProps {
  token: string;
}

export const FeatureStoreViewer: React.FC<FeatureStoreViewerProps> = ({ token }) => {
  const [features, setFeatures] = useState<FeatureValue[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const loadFeatures = async () => {
      setLoading(true);
      try {
        const data = await fetchFeatures(token);
        setFeatures(data);
      } catch (error) {
        console.error('Failed to load features:', error);
        setFeatures([]);
      } finally {
        setLoading(false);
      }
    };

    if (token) {
      loadFeatures();
      const interval = setInterval(loadFeatures, 30000); // Refresh every 30s
      return () => clearInterval(interval);
    }
  }, [token]);

  // Get unique categories
  const categories = ['all', ...new Set(features.map(f => f.category))];

  // Filter features
  const filteredFeatures = features.filter(feature => {
    const matchesCategory =
      categoryFilter === 'all' || feature.category === categoryFilter;
    const matchesSearch =
      searchQuery === '' ||
      feature.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  // Group features by category
  const groupedFeatures = filteredFeatures.reduce((acc, feature) => {
    if (!acc[feature.category]) {
      acc[feature.category] = [];
    }
    acc[feature.category].push(feature);
    return acc;
  }, {} as Record<string, FeatureValue[]>);

  const formatValue = (feature: FeatureValue) => {
    if (typeof feature.value === 'boolean') {
      return feature.value ? '✓ True' : '✗ False';
    }
    if (typeof feature.value === 'number') {
      return feature.value.toFixed(4);
    }
    return String(feature.value);
  };

  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'text-green-600 bg-green-100';
    if (confidence >= 0.7) return 'text-blue-600 bg-blue-100';
    if (confidence >= 0.5) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const getFeatureTypeIcon = (type: string) => {
    switch (type.toUpperCase()) {
      case 'NUMERIC':
        return '🔢';
      case 'CATEGORICAL':
        return '📂';
      case 'BOOLEAN':
        return '✓';
      case 'TIMESTAMP':
        return '⏰';
      case 'VECTOR':
        return '📊';
      default:
        return '•';
    }
  };

  if (loading) {
    return <div className="p-4">Loading feature store...</div>;
  }

  return (
    <div className="feature-store-viewer">
      <div className="viewer-header">
        <h3 className="text-xl font-bold">Feature Store - {token}</h3>
        <div className="feature-count text-sm text-gray-500">
          {features.length} features available
        </div>
      </div>

      {/* Filters */}
      <div className="filters-section">
        {/* Search */}
        <input
          type="text"
          placeholder="Search features..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="search-input"
        />

        {/* Category Filter */}
        <div className="category-filters">
          {categories.map(category => (
            <button
              key={category}
              onClick={() => setCategoryFilter(category)}
              className={`filter-button ${
                categoryFilter === category ? 'active' : ''
              }`}
            >
              {category === 'all' ? 'All Categories' : category}
            </button>
          ))}
        </div>
      </div>

      {/* Features List */}
      {features.length === 0 ? (
        <div className="empty-state">
          <div className="text-4xl mb-2">📦</div>
          <div className="text-gray-500">No features available for this token</div>
          <div className="text-sm text-gray-400">
            Features are generated when the scanner runs
          </div>
        </div>
      ) : filteredFeatures.length === 0 ? (
        <div className="empty-state">
          <div className="text-4xl mb-2">🔍</div>
          <div className="text-gray-500">No features match your filters</div>
        </div>
      ) : (
        <div className="features-groups">
          {Object.entries(groupedFeatures).map(([category, categoryFeatures]) => (
            <div key={category} className="feature-group">
              <h4 className="group-title">{category}</h4>
              <div className="features-list">
                {categoryFeatures.map((feature, idx) => (
                  <div key={`${feature.name}-${idx}`} className="feature-card">
                    <div className="feature-header">
                      <div className="feature-name">
                        <span className="type-icon">
                          {getFeatureTypeIcon(feature.feature_type)}
                        </span>
                        <span className="name-text">{feature.name}</span>
                      </div>
                      <span
                        className={`confidence-badge ${getConfidenceColor(
                          feature.confidence
                        )}`}
                      >
                        {(feature.confidence * 100).toFixed(0)}%
                      </span>
                    </div>

                    <div className="feature-value">{formatValue(feature)}</div>

                    <div className="feature-meta">
                      <span className="meta-item">
                        <span className="meta-label">Type:</span>
                        <span className="meta-value">{feature.feature_type}</span>
                      </span>
                      <span className="meta-item">
                        <span className="meta-label">Updated:</span>
                        <span className="meta-value">
                          {formatTimestamp(feature.timestamp)}
                        </span>
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Schema Info */}
      <div className="schema-info">
        <h4 className="font-semibold mb-2">Feature Store Info</h4>
        <ul className="text-sm space-y-1">
          <li>
            • <strong>Categories:</strong> MARKET, LIQUIDITY, ORDERFLOW, DERIVATIVES,
            SENTIMENT, ONCHAIN, TECHNICAL, QUALITY, SCORING
          </li>
          <li>
            • <strong>Types:</strong> NUMERIC (numbers), CATEGORICAL (labels), BOOLEAN
            (true/false), TIMESTAMP (dates), VECTOR (arrays)
          </li>
          <li>
            • <strong>Confidence:</strong> Statistical confidence in the feature value (0-100%)
          </li>
          <li>
            • <strong>Point-in-time:</strong> All features include timestamps for historical
            queries
          </li>
        </ul>
      </div>
    </div>
  );
};
