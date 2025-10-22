import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchExperiments, fetchAllTags } from '../api';
import { ExperimentSummary } from '../types';
import './ExperimentsRegistry.css';

interface Props {
  onSelectExperiment: (hash: string) => void;
}

export function ExperimentsRegistry({ onSelectExperiment }: Props) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTag, setSelectedTag] = useState<string>('');

  const experimentsQuery = useQuery<ExperimentSummary[]>({
    queryKey: ['experiments', selectedTag, searchQuery],
    queryFn: () => fetchExperiments({ 
      tag: selectedTag || undefined, 
      search: searchQuery || undefined,
      limit: 100,
    }),
  });

  const tagsQuery = useQuery({
    queryKey: ['experiment-tags'],
    queryFn: fetchAllTags,
  });

  const handleTagClick = (tag: string) => {
    setSelectedTag(tag === selectedTag ? '' : tag);
  };

  return (
    <div className="experiments-registry">
      <div className="registry-header">
        <h2>Experiments Registry</h2>
        <div className="registry-controls">
          <input
            type="text"
            className="search-input"
            placeholder="Search experiments..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Tags filter */}
      {tagsQuery.data && tagsQuery.data.tags.length > 0 && (
        <div className="tags-filter">
          <span className="filter-label">Filter by tag:</span>
          <div className="tag-buttons">
            {tagsQuery.data.tags.slice(0, 10).map((tag) => (
              <button
                key={tag}
                className={`tag-button ${selectedTag === tag ? 'active' : ''}`}
                onClick={() => handleTagClick(tag)}
              >
                {tag}
                <span className="tag-count">({tagsQuery.data.tag_counts[tag]})</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Experiments list */}
      <div className="experiments-list">
        {experimentsQuery.isLoading && <div className="loading">Loading experiments...</div>}
        
        {experimentsQuery.isError && (
          <div className="error">
            Failed to load experiments: {(experimentsQuery.error as Error).message}
          </div>
        )}

        {experimentsQuery.data && experimentsQuery.data.length === 0 && (
          <div className="empty-state">
            <p>No experiments found.</p>
            {(searchQuery || selectedTag) && (
              <button onClick={() => { setSearchQuery(''); setSelectedTag(''); }}>
                Clear filters
              </button>
            )}
          </div>
        )}

        {experimentsQuery.data && experimentsQuery.data.map((exp) => (
          <div
            key={exp.config_hash}
            className="experiment-card"
            onClick={() => onSelectExperiment(exp.short_hash)}
          >
            <div className="card-header">
              <div className="hash-display">
                <code>{exp.short_hash}</code>
                {exp.has_results && <span className="results-badge">✓ Results</span>}
              </div>
              <div className="created-date">
                {new Date(exp.created_at).toLocaleDateString()}
              </div>
            </div>
            
            <div className="card-body">
              {exp.description && (
                <p className="description">{exp.description}</p>
              )}
              
              <div className="metadata">
                <span className="feature-count">
                  {exp.feature_count} features
                </span>
                {exp.tags.length > 0 && (
                  <div className="tags">
                    {exp.tags.map((tag) => (
                      <span key={tag} className="tag">{tag}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
