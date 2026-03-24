/**
 * MetricsGrid.jsx — Revamped metrics with visual bars
 */

import React from 'react';

function MetricTile({ label, value, rawValue, barColor }) {
  const pct = typeof rawValue === 'number' ? Math.round(rawValue * 100) : null;
  return (
    <div className="metric-tile">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
      {pct !== null && (
        <div className="metric-bar-track">
          <div
            className="metric-bar-fill"
            style={{ width: `${pct}%`, background: barColor || 'var(--accent)' }}
          />
        </div>
      )}
    </div>
  );
}

export default function MetricsGrid({ metrics }) {
  if (!metrics || Object.keys(metrics).length === 0) return null;

  const credibility = metrics.credibility_score ?? metrics.credibility ?? null;
  const fallacies   = metrics.logical_fallacies;
  const argQuality  = metrics.argument_quality ?? null;

  const fallacyCount = Array.isArray(fallacies)
    ? fallacies.length
    : typeof fallacies === 'number' ? fallacies : null;

  const tiles = [
    credibility !== null && {
      label: 'Evidence Credibility',
      value: `${Math.round((credibility || 0) * 100)}%`,
      rawValue: credibility,
      barColor: credibility > 0.6 ? 'var(--pro)' : 'var(--amber)',
    },
    argQuality !== null && {
      label: 'Argument Quality',
      value: `${Math.round((argQuality || 0) * 100)}%`,
      rawValue: argQuality,
      barColor: argQuality > 0.6 ? 'var(--pro)' : 'var(--amber)',
    },
    fallacyCount !== null && {
      label: 'Logical Fallacies',
      value: fallacyCount,
      rawValue: null,
      barColor: null,
    },
  ].filter(Boolean);

  if (tiles.length === 0) return null;

  return (
    <div className="metrics-section">
      <div className="section-label" style={{ marginBottom: '12px' }}>Intelligence Metrics</div>
      <div className="metrics-grid">
        {tiles.map(tile => (
          <MetricTile key={tile.label} {...tile} />
        ))}
      </div>

      {/* Fallacy list if any */}
      {Array.isArray(fallacies) && fallacies.length > 0 && (
        <div className="fallacy-list">
          <div className="fallacy-list-label">Detected Fallacies:</div>
          <div className="fallacy-tags">
            {fallacies.map((f, i) => (
              <span key={i} className="fallacy-tag">{f}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
