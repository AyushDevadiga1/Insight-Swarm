/**
 * ReasoningPanel.jsx
 * 
 * Collapsible moderator analysis.
 * Progressive disclosure: hidden by default, user clicks to expand.
 * This means the browser doesn't paint this expensive text block
 * until the user actually wants it.
 * 
 * Uses CSS content-visibility: auto when collapsed so the browser
 * skips rendering entirely while hidden.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

export default function ReasoningPanel({ result }) {
  const [expanded, setExpanded] = useState(false);
  const text = result?.moderator_reasoning || result?.reasoning;
  if (!text) return null;

  return (
    <div className="reasoning-panel">
      <button
        className="reasoning-toggle"
        onClick={() => setExpanded(v => !v)}
        aria-expanded={expanded}
      >
        <span className="section-label">Moderator Analysis</span>
        <div className="reasoning-toggle-right">
          <span className="reasoning-toggle-hint">
            {expanded ? 'Hide' : 'View reasoning'}
          </span>
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {/* content-visibility: auto is set via CSS class .reasoning-body--hidden */}
      <div
        className={`reasoning-body ${expanded ? 'reasoning-body--open' : 'reasoning-body--hidden'}`}
        aria-hidden={!expanded}
      >
        <p className="reasoning-text">{text}</p>

        {result?.metrics?.confidence_breakdown && (
          <div className="reasoning-breakdown">
            <div className="reasoning-breakdown-title">Confidence Breakdown</div>
            <div className="reasoning-breakdown-grid">
              {Object.entries({
                'Argument Quality': result.metrics.confidence_breakdown.argument_quality_score,
                'Source Verification': result.metrics.confidence_breakdown.verification_score,
                'Source Trust': result.metrics.confidence_breakdown.trust_score,
                'Consensus': result.metrics.confidence_breakdown.consensus_score,
              }).map(([label, value]) => (
                <div className="breakdown-item" key={label}>
                  <span className="breakdown-label">{label}</span>
                  <div className="breakdown-bar-track">
                    <div
                      className="breakdown-bar-fill"
                      style={{ width: `${Math.round((value || 0) * 100)}%` }}
                    />
                  </div>
                  <span className="breakdown-value">{Math.round((value || 0) * 100)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
