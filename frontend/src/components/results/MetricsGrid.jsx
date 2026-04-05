/**
 * MetricsGrid.jsx — Extended with novelty module outputs
 * Shows: credibility, argument quality, fallacies,
 *        argumentation analysis (pro/con quality), and
 *        confidence calibration metadata.
 */

import React, { useState } from 'react';

function MetricTile({ label, value, rawValue, barColor, sub }) {
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
      {sub && (
        <span style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--mono)', marginTop: 2 }}>
          {sub}
        </span>
      )}
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div className="section-label" style={{ marginBottom: '10px' }}>{children}</div>
  );
}

/* ── Argumentation Analysis Block ── */
function ArgumentationBlock({ data }) {
  if (!data) return null;
  const {
    pro_avg_quality, con_avg_quality, quality_gap,
    pro_fallacy_count, con_fallacy_count,
    debate_quality, higher_quality_side,
  } = data;

  const qualityColor = (q) => q >= 0.6 ? 'var(--pro)' : q >= 0.4 ? 'var(--warning)' : 'var(--con)';

  return (
    <div style={{ width: '100%', maxWidth: 520, marginTop: 4 }}>
      <SectionLabel>Argumentation Analysis</SectionLabel>
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
          padding: '14px 18px',
        }}
      >
        {/* Quality row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text-3)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              ProAgent quality
            </div>
            <div style={{ fontSize: 20, fontWeight: 600, color: qualityColor(pro_avg_quality), fontFamily: 'var(--mono)' }}>
              {Math.round((pro_avg_quality || 0) * 100)}%
            </div>
            <div style={{ height: 2, background: 'var(--border-md)', borderRadius: 1, marginTop: 5 }}>
              <div style={{ height: '100%', width: `${Math.round((pro_avg_quality || 0) * 100)}%`, background: qualityColor(pro_avg_quality), borderRadius: 1, transition: 'width 0.8s ease' }} />
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text-3)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              ConAgent quality
            </div>
            <div style={{ fontSize: 20, fontWeight: 600, color: qualityColor(con_avg_quality), fontFamily: 'var(--mono)' }}>
              {Math.round((con_avg_quality || 0) * 100)}%
            </div>
            <div style={{ height: 2, background: 'var(--border-md)', borderRadius: 1, marginTop: 5 }}>
              <div style={{ height: '100%', width: `${Math.round((con_avg_quality || 0) * 100)}%`, background: qualityColor(con_avg_quality), borderRadius: 1, transition: 'width 0.8s ease' }} />
            </div>
          </div>
        </div>

        {/* Meta row */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', borderTop: '1px solid var(--border)', paddingTop: 10 }}>
          <span style={pillStyle('var(--accent-dim)', 'var(--accent)', 'var(--accent-border)')}>
            Quality gap: {Math.round((quality_gap || 0) * 100)}%
          </span>
          <span style={pillStyle('var(--pro-dim)', 'var(--pro)', 'var(--pro-border)')}>
            Better side: {higher_quality_side || '—'}
          </span>
          <span style={pillStyle(
            debate_quality === 'high' ? 'var(--pro-dim)' : 'var(--mod-dim)',
            debate_quality === 'high' ? 'var(--pro)' : 'var(--mod)',
            debate_quality === 'high' ? 'var(--pro-border)' : 'var(--mod-border)',
          )}>
            Debate: {debate_quality || 'low'}
          </span>
          {(pro_fallacy_count > 0 || con_fallacy_count > 0) && (
            <span style={pillStyle('var(--con-dim)', 'var(--con)', 'var(--con-border)')}>
              Fallacies: Pro {pro_fallacy_count} / Con {con_fallacy_count}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Calibration Block ── */
function CalibrationBlock({ data }) {
  if (!data) return null;
  const {
    raw_confidence, calibrated_confidence, adjustment,
    adjustment_type, underconfidence_detected,
    source_quality_score, debate_asymmetry, claim_type,
  } = data;

  const wasAdjusted = adjustment_type !== 'none' && Math.abs(adjustment || 0) > 0.001;

  return (
    <div style={{ width: '100%', maxWidth: 520, marginTop: 4 }}>
      <SectionLabel>Confidence Calibration</SectionLabel>
      <div
        style={{
          background: 'var(--bg-card)',
          border: `1px solid ${wasAdjusted ? 'var(--mod-border)' : 'var(--border)'}`,
          borderLeft: `3px solid ${wasAdjusted ? 'var(--mod)' : 'var(--border)'}`,
          borderRadius: '0 var(--radius-lg) var(--radius-lg) 0',
          padding: '14px 18px',
        }}
      >
        {/* Confidence flow */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text-3)', marginBottom: 3 }}>Raw</div>
            <div style={{ fontSize: 18, fontFamily: 'var(--mono)', fontWeight: 600, color: 'var(--text-2)' }}>
              {Math.round((raw_confidence || 0) * 100)}%
            </div>
          </div>
          <div style={{ flex: 1, textAlign: 'center', fontSize: 18, color: wasAdjusted ? 'var(--mod)' : 'var(--text-4)' }}>
            {wasAdjusted ? (adjustment > 0 ? '↑' : '↓') : '→'}
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text-3)', marginBottom: 3 }}>Calibrated</div>
            <div style={{ fontSize: 18, fontFamily: 'var(--mono)', fontWeight: 600, color: wasAdjusted ? 'var(--mod)' : 'var(--text-2)' }}>
              {Math.round((calibrated_confidence || 0) * 100)}%
            </div>
          </div>
          {wasAdjusted && (
            <span style={pillStyle('var(--mod-dim)', 'var(--mod)', 'var(--mod-border)')}>
              {adjustment > 0 ? '+' : ''}{Math.round((adjustment || 0) * 100)}%
            </span>
          )}
        </div>

        {/* Meta */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', borderTop: '1px solid var(--border)', paddingTop: 10 }}>
          {claim_type && (
            <span style={pillStyle('var(--bg-elevated)', 'var(--text-3)', 'var(--border)')}>
              claim type: {claim_type}
            </span>
          )}
          <span style={pillStyle('var(--bg-elevated)', 'var(--text-3)', 'var(--border)')}>
            source quality: {Math.round((source_quality_score || 0) * 100)}%
          </span>
          <span style={pillStyle('var(--bg-elevated)', 'var(--text-3)', 'var(--border)')}>
            debate asymmetry: {Math.round((debate_asymmetry || 0) * 100)}%
          </span>
          {underconfidence_detected && (
            <span style={pillStyle('var(--mod-dim)', 'var(--mod)', 'var(--mod-border)')}>
              underconfidence detected
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function pillStyle(bg, color, border) {
  return {
    display: 'inline-block',
    padding: '2px 8px',
    background: bg,
    color,
    border: `1px solid ${border}`,
    borderRadius: 20,
    fontSize: 9,
    fontFamily: 'var(--mono)',
    letterSpacing: '0.04em',
  };
}

export default function MetricsGrid({ metrics }) {
  if (!metrics || Object.keys(metrics).length === 0) return null;

  const credibility  = metrics.credibility_score ?? metrics.credibility ?? null;
  const argQuality   = metrics.argument_quality ?? null;
  const fallacies    = metrics.logical_fallacies;
  const argAnalysis  = metrics.argumentation_analysis ?? null;
  const calibration  = metrics.calibration ?? null;

  const fallacyCount = Array.isArray(fallacies)
    ? fallacies.length
    : typeof fallacies === 'number' ? fallacies : null;

  const tiles = [
    credibility !== null && {
      label: 'Evidence Credibility',
      value: `${Math.round((credibility || 0) * 100)}%`,
      rawValue: credibility,
      barColor: credibility > 0.6 ? 'var(--pro)' : 'var(--warning)',
    },
    argQuality !== null && {
      label: 'Argument Quality',
      value: `${Math.round((argQuality || 0) * 100)}%`,
      rawValue: argQuality,
      barColor: argQuality > 0.6 ? 'var(--pro)' : 'var(--warning)',
    },
    fallacyCount !== null && {
      label: 'Logical Fallacies',
      value: fallacyCount,
      rawValue: null,
    },
  ].filter(Boolean);

  const hasCoreMetrics = tiles.length > 0 || Array.isArray(fallacies);

  return (
    <div style={{ width: '100%', maxWidth: 520, display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Core metrics tiles ── */}
      {hasCoreMetrics && (
        <div className="metrics-section">
          <SectionLabel>Intelligence Metrics</SectionLabel>
          {tiles.length > 0 && (
            <div className="metrics-grid">
              {tiles.map(tile => (
                <MetricTile key={tile.label} {...tile} />
              ))}
            </div>
          )}
          {Array.isArray(fallacies) && fallacies.length > 0 && (
            <div className="fallacy-list" style={{ marginTop: 10 }}>
              <div className="fallacy-list-label">Detected Fallacies:</div>
              <div className="fallacy-tags">
                {fallacies.map((f, i) => (
                  <span key={i} className="fallacy-tag">{f}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Argumentation Analysis (novelty module) ── */}
      <ArgumentationBlock data={argAnalysis} />

      {/* ── Confidence Calibration (novelty module) ── */}
      <CalibrationBlock data={calibration} />

    </div>
  );
}
