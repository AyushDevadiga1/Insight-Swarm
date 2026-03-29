/**
 * SourceTable.jsx
 * 
 * Displays URL verification results with:
 * - Trust tier badge (AUTHORITATIVE / CREDIBLE / GENERAL / UNRELIABLE)
 * - Status badge (VERIFIED / FAILED / TIMEOUT / PAYWALL)
 * - PRO/CON agent label
 * - Error message when failed
 * 
 * Performance: `contain: strict` on the table container.
 * Virtual scrolling kicks in at > 20 rows (via CSS, not a library,
 * since source tables rarely exceed 30 rows in practice).
 */

import React, { useState } from 'react';
import { ExternalLink, Info } from 'lucide-react';

const STATUS_CONFIG = {
  VERIFIED:           { label: 'VERIFIED',   color: 'var(--pro)',   bg: 'rgba(34,197,94,0.08)' },
  NOT_FOUND:          { label: 'NOT FOUND',  color: 'var(--con)',   bg: 'rgba(239,68,68,0.08)' },
  TIMEOUT:            { label: 'TIMEOUT',    color: 'var(--amber)', bg: 'rgba(245,158,11,0.08)' },
  CONTENT_MISMATCH:   { label: 'MISMATCH',   color: 'var(--amber)', bg: 'rgba(245,158,11,0.08)' },
  INVALID_URL:        { label: 'INVALID',    color: '#555',         bg: 'rgba(85,85,85,0.08)' },
  PAYWALL_RESTRICTED: { label: 'PAYWALL',    color: 'var(--amber)', bg: 'rgba(245,158,11,0.08)' },
  ERROR:              { label: 'ERROR',      color: 'var(--con)',   bg: 'rgba(239,68,68,0.08)' },
};

const TRUST_CONFIG = {
  AUTHORITATIVE: { label: 'AUTH',    color: '#22c55e' },
  CREDIBLE:      { label: 'CRED',    color: '#3b82f6' },
  GENERAL:       { label: 'GEN',     color: '#888' },
  UNDIRECTED:    { label: 'SOCIAL',  color: '#f59e0b' },
  UNRELIABLE:    { label: 'UNREL',   color: '#ef4444' },
};

function clip(url, n = 55) {
  if (!url) return '';
  return url.length > n ? url.slice(0, n - 1) + '…' : url;
}

// Stream sources arrive one by one during verification.
// This component can be used both during streaming (from store.sourceResults)
// and after completion (from result.verification_results).
export default function SourceTable({ sources }) {
  const [filter, setFilter] = useState('ALL'); // ALL | PRO | CON | FAILED

  if (!sources || sources.length === 0) return null;

  const proCount = sources.filter(s => s.agent_source === 'PRO').length;
  const conCount = sources.filter(s => s.agent_source === 'CON').length;
  const verifiedCount = sources.filter(s => s.status === 'VERIFIED').length;

  const filtered = filter === 'ALL'    ? sources
    : filter === 'PRO'   ? sources.filter(s => s.agent_source === 'PRO')
    : filter === 'CON'   ? sources.filter(s => s.agent_source === 'CON')
    : sources.filter(s => s.status !== 'VERIFIED');

  return (
    <div className="sources-section">
      {/* Header with summary stats */}
      <div className="sources-header">
        <div className="section-label">Source Verification</div>
        <div className="sources-summary">
          <span className="sources-stat">
            <span className="sources-stat-val" style={{ color: 'var(--pro)' }}>{verifiedCount}</span> verified
          </span>
          <span className="sources-stat">
            <span className="sources-stat-val">{sources.length - verifiedCount}</span> failed
          </span>
          <span className="sources-stat">
            <span className="sources-stat-val" style={{ color: 'var(--pro)' }}>{proCount}</span> PRO ·
            <span className="sources-stat-val" style={{ color: 'var(--con)', marginLeft: 4 }}>{conCount}</span> CON
          </span>
        </div>
      </div>

      {/* Filter pills */}
      <div className="sources-filters">
        {['ALL', 'PRO', 'CON', 'FAILED'].map(f => (
          <button
            key={f}
            className={`filter-pill ${filter === f ? 'filter-pill--active' : ''}`}
            onClick={() => setFilter(f)}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Table with CSS containment */}
      <div className="sources-table">
        {filtered.map((src, i) => {
          const sc = STATUS_CONFIG[src.status] || STATUS_CONFIG.ERROR;
          const tc = TRUST_CONFIG[src.trust_tier] || TRUST_CONFIG.GENERAL;
          const isVerified = src.status === 'VERIFIED';

          return (
            <div className="source-row" key={i}>
              {/* Row number */}
              <span className="source-num">{String(i + 1).padStart(2, '0')}</span>

              {/* Agent badge */}
              <span
                className="source-agent"
                style={{ color: src.agent_source === 'PRO' ? 'var(--pro)' : 'var(--con)' }}
              >
                {src.agent_source || '—'}
              </span>

              {/* URL */}
              <div className="source-url-wrap">
                <a
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`source-url ${!isVerified ? 'source-url--failed' : ''}`}
                  title={src.url}
                >
                  {clip(src.url)}
                  <ExternalLink size={10} className="source-ext-icon" />
                </a>
                <div className="source-meta">
                  {!isVerified && src.error && src.status === 'CONTENT_MISMATCH' ? (
                    <span className="source-error-tooltip" title={src.error}>
                      <Info size={12} className="info-icon" /> Temporal Mismatch
                    </span>
                  ) : !isVerified && src.error ? (
                    <span className="source-error">{src.error}</span>
                  ) : null}
                </div>
              </div>

              {/* Trust tier */}
              <span className="source-trust" style={{ color: tc.color }}>{tc.label}</span>

              {/* Status badge */}
              <span
                className="source-badge"
                style={{ color: sc.color, background: sc.bg, borderColor: sc.color }}
              >
                {sc.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
