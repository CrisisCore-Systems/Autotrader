import { useState } from 'react';
import { ExperimentsRegistry } from './ExperimentsRegistry';
import { ExperimentDetail } from './ExperimentDetail';
import { ExperimentCompare } from './ExperimentCompare';
import { exportExperiment } from '../api';
import './ExperimentsWorkspace.css';

type ViewMode = 'registry' | 'detail' | 'compare';

export function ExperimentsWorkspace() {
  const [viewMode, setViewMode] = useState<ViewMode>('registry');
  const [selectedHash, setSelectedHash] = useState<string | null>(null);
  const [compareHashes, setCompareHashes] = useState<[string, string] | null>(null);

  const handleSelectExperiment = (hash: string) => {
    setSelectedHash(hash);
    setViewMode('detail');
  };

  const handleCompare = (hash: string) => {
    // If we have a selected experiment, compare with it
    if (selectedHash && selectedHash !== hash) {
      setCompareHashes([selectedHash, hash]);
      setViewMode('compare');
    } else {
      // Otherwise, prompt for a second experiment
      // In a real app, this would show a modal to select another experiment
      alert('Please select another experiment from the registry to compare');
    }
  };

  const handleExport = async (hash: string) => {
    try {
      const result = await exportExperiment(hash, 'json', {
        includeMetrics: true,
        includeConfig: true,
      });
      
      if (result.status === 'success') {
        alert(`Experiment exported successfully to ${result.file_path}`);
      } else if (result.status === 'not_implemented') {
        alert(result.message);
      }
    } catch (error) {
      alert(`Export failed: ${(error as Error).message}`);
    }
  };

  const handleBackToRegistry = () => {
    setViewMode('registry');
    setSelectedHash(null);
    setCompareHashes(null);
  };

  return (
    <div className="experiments-workspace">
      {/* Navigation breadcrumb */}
      <div className="workspace-nav">
        <button onClick={handleBackToRegistry} className="nav-button">
          ← Back to Registry
        </button>
        <div className="breadcrumb">
          <span className={viewMode === 'registry' ? 'active' : ''}>Registry</span>
          {selectedHash && (
            <>
              <span className="separator">/</span>
              <span className={viewMode === 'detail' ? 'active' : ''}>
                Detail ({selectedHash})
              </span>
            </>
          )}
          {compareHashes && (
            <>
              <span className="separator">/</span>
              <span className={viewMode === 'compare' ? 'active' : ''}>
                Compare
              </span>
            </>
          )}
        </div>
      </div>

      {/* Content area */}
      <div className="workspace-content">
        {viewMode === 'registry' && (
          <ExperimentsRegistry onSelectExperiment={handleSelectExperiment} />
        )}

        {viewMode === 'detail' && selectedHash && (
          <ExperimentDetail
            configHash={selectedHash}
            onCompare={handleCompare}
            onExport={handleExport}
          />
        )}

        {viewMode === 'compare' && compareHashes && (
          <ExperimentCompare
            hash1={compareHashes[0]}
            hash2={compareHashes[1]}
            onClose={handleBackToRegistry}
          />
        )}
      </div>
    </div>
  );
}
