/* Alert Rule Builder Component */

import React, { useState } from 'react';
import './RuleBuilder.css';

interface AlertRule {
  id?: string;
  description: string;
  enabled: boolean;
  condition: {
    metric: string;
    operator: string;
    threshold: number | string;
  };
  where: Record<string, any>;
  severity: 'info' | 'warning' | 'high' | 'critical';
  channels: string[];
  suppression_duration: number;
  tags: string[];
  version: string;
}

interface RuleBuilderProps {
  onSave: (rule: AlertRule) => void;
  onCancel: () => void;
  initialRule?: AlertRule;
}

export const RuleBuilder: React.FC<RuleBuilderProps> = ({ 
  onSave, 
  onCancel, 
  initialRule 
}) => {
  const [rule, setRule] = useState<AlertRule>(initialRule || {
    description: '',
    enabled: true,
    condition: {
      metric: 'gem_score',
      operator: 'gte',
      threshold: 70
    },
    where: {},
    severity: 'warning',
    channels: [],
    suppression_duration: 3600,
    tags: [],
    version: 'v2'
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const metrics = [
    { value: 'gem_score', label: 'GemScore' },
    { value: 'confidence', label: 'Confidence' },
    { value: 'liquidity_usd', label: 'Liquidity (USD)' },
    { value: 'sentiment_score', label: 'Sentiment Score' },
    { value: 'volume_24h', label: '24h Volume' },
  ];

  const operators = [
    { value: 'lt', label: '<' },
    { value: 'lte', label: '≤' },
    { value: 'eq', label: '=' },
    { value: 'neq', label: '≠' },
    { value: 'gte', label: '≥' },
    { value: 'gt', label: '>' },
  ];

  const severities = [
    { value: 'info', label: 'Info', color: '#2196F3' },
    { value: 'warning', label: 'Warning', color: '#FF9800' },
    { value: 'high', label: 'High', color: '#FF5722' },
    { value: 'critical', label: 'Critical', color: '#F44336' },
  ];

  const availableChannels = [
    { value: 'telegram', label: 'Telegram' },
    { value: 'slack', label: 'Slack' },
    { value: 'email', label: 'Email' },
    { value: 'webhook', label: 'Webhook' },
  ];

  const validateRule = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!rule.description.trim()) {
      newErrors.description = 'Description is required';
    }

    if (!rule.condition.threshold && rule.condition.threshold !== 0) {
      newErrors.threshold = 'Threshold is required';
    }

    if (rule.channels.length === 0) {
      newErrors.channels = 'At least one channel is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = () => {
    if (validateRule()) {
      onSave(rule);
    }
  };

  const toggleChannel = (channel: string) => {
    const newChannels = rule.channels.includes(channel)
      ? rule.channels.filter(c => c !== channel)
      : [...rule.channels, channel];
    
    setRule({ ...rule, channels: newChannels });
  };

  const addTag = (tag: string) => {
    if (tag && !rule.tags.includes(tag)) {
      setRule({ ...rule, tags: [...rule.tags, tag] });
    }
  };

  const removeTag = (tag: string) => {
    setRule({ ...rule, tags: rule.tags.filter(t => t !== tag) });
  };

  return (
    <div className="rule-builder">
      <h2>{initialRule ? 'Edit Alert Rule' : 'Create Alert Rule'}</h2>

      <div className="form-group">
        <label htmlFor="description">Description *</label>
        <input
          id="description"
          type="text"
          value={rule.description}
          onChange={e => setRule({ ...rule, description: e.target.value })}
          placeholder="e.g., High GemScore Alert"
          className={errors.description ? 'error' : ''}
        />
        {errors.description && <span className="error-message">{errors.description}</span>}
      </div>

      <div className="form-group">
        <label>
          <input
            type="checkbox"
            checked={rule.enabled}
            onChange={e => setRule({ ...rule, enabled: e.target.checked })}
          />
          Enabled
        </label>
      </div>

      <div className="condition-section">
        <h3>Trigger Condition</h3>
        <div className="condition-builder">
          <select
            value={rule.condition.metric}
            onChange={e => setRule({
              ...rule,
              condition: { ...rule.condition, metric: e.target.value }
            })}
          >
            {metrics.map(m => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>

          <select
            value={rule.condition.operator}
            onChange={e => setRule({
              ...rule,
              condition: { ...rule.condition, operator: e.target.value }
            })}
          >
            {operators.map(op => (
              <option key={op.value} value={op.value}>{op.label}</option>
            ))}
          </select>

          <input
            type="number"
            value={rule.condition.threshold}
            onChange={e => setRule({
              ...rule,
              condition: { ...rule.condition, threshold: parseFloat(e.target.value) }
            })}
            placeholder="Threshold"
            className={errors.threshold ? 'error' : ''}
          />
        </div>
        {errors.threshold && <span className="error-message">{errors.threshold}</span>}
      </div>

      <div className="form-group">
        <label>Severity</label>
        <div className="severity-selector">
          {severities.map(s => (
            <button
              key={s.value}
              className={`severity-btn ${rule.severity === s.value ? 'active' : ''}`}
              style={{ 
                backgroundColor: rule.severity === s.value ? s.color : 'transparent',
                borderColor: s.color,
                color: rule.severity === s.value ? 'white' : s.color
              }}
              onClick={() => setRule({ ...rule, severity: s.value as any })}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="form-group">
        <label>Notification Channels *</label>
        <div className="channels-selector">
          {availableChannels.map(ch => (
            <label key={ch.value} className="channel-option">
              <input
                type="checkbox"
                checked={rule.channels.includes(ch.value)}
                onChange={() => toggleChannel(ch.value)}
              />
              {ch.label}
            </label>
          ))}
        </div>
        {errors.channels && <span className="error-message">{errors.channels}</span>}
      </div>

      <div className="form-group">
        <label htmlFor="suppression">Suppression Duration (seconds)</label>
        <input
          id="suppression"
          type="number"
          value={rule.suppression_duration}
          onChange={e => setRule({ ...rule, suppression_duration: parseInt(e.target.value) })}
          min="0"
        />
        <small>Minimum time between repeated alerts (dedupe window)</small>
      </div>

      <div className="form-group">
        <label htmlFor="tags">Tags</label>
        <div className="tags-container">
          {rule.tags.map(tag => (
            <span key={tag} className="tag">
              {tag}
              <button onClick={() => removeTag(tag)} className="tag-remove">×</button>
            </span>
          ))}
        </div>
        <input
          id="tags"
          type="text"
          placeholder="Add tag and press Enter"
          onKeyPress={e => {
            if (e.key === 'Enter') {
              addTag((e.target as HTMLInputElement).value);
              (e.target as HTMLInputElement).value = '';
            }
          }}
        />
      </div>

      <div className="form-actions">
        <button onClick={handleSave} className="btn-primary">
          {initialRule ? 'Update Rule' : 'Create Rule'}
        </button>
        <button onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </div>
  );
};
