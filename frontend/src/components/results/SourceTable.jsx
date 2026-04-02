/**
 * SourceTable.jsx — v3
 */

import React, { useState } from 'react';

export default function SourceTable({ sources = [] }) {
  const [filter, setFilter] = useState('all');
  if (!sources || sources.length === 0) return null;

  const verified = sources.filter(s => s.status === 'VERIFIED');
  const failed   = sources.filter(s => s.status !== 'VERIFIED');

  const displayed = filter === 'ok'   ? verified
                  : filter === 'fail' ? failed
                  : sources;

  function clip(url = '', n = 55) {
    return url.length > n ? url.slice(0, n - 1) + '…' : url;
  }

  return (
    <div className="sources-section">
      <div className="sources-header">
        <div className="section-label">Source verification</div>
        <div className="sources-summary">
          <span className="sources-stat">
            <span className="sources-stat-val">{verified.length}</span>/{sources.length} verified
          </span>
        </div>
      </div>

      <div className="sources-filters">
        {[['all', 'All'], ['ok', 'Verified'], ['fail', 'Failed']].map(([val, label]) => (
          <button
            key={val}
            className={`filter-pill ${filter === val ? 'active' : ''}`}
            onClick={() => setFilter(val)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="sources-table">
        {displayed.map((src, i) => {
          const ok  = src.status === 'VERIFIED';
          const url = src.url || '';
          return (
            <div className="source-row" key={i}>
              <span className="source-num">{String(i + 1).padStart(2, '0')}</span>
              <span className="source-agent" style={{ color: ok ? 'var(--pro)' : 'var(--con)' }}>
                {src.agent === 'PRO' ? '🛡️' : src.agent === 'CON' ? '⚔️' : '🔬'}
              </span>
              <div className="source-url-wrap">
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`source-url ${!ok ? 'failed' : ''}`}
                >
                  {clip(url)}
                </a>
                {!ok && src.error && (
                  <span className="source-error">{src.error}</span>
                )}
              </div>
              <span className={`source-badge ${ok ? 'ok' : 'fail'}`}>
                {ok ? 'Verified' : 'Failed'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
