/**
 * HITLPanel.jsx — Human-in-the-Loop Review Panel
 *
 * Rendered when SSE emits `human_review_required`.
 * Lets a human reviewer:
 *   1. Override individual source verification statuses
 *   2. Override the final verdict directly
 *   3. Submit overrides → POST /api/debate/resume/{thread_id}
 *   4. Skip review → resumes with no changes
 */

import React, { useState } from 'react';
import { useDebateStore } from '../../store/useDebateStore';

const VERDICT_OPTIONS = [
  { value: '',                       label: 'No override — let Moderator decide' },
  { value: 'TRUE',                   label: '✅ TRUE' },
  { value: 'FALSE',                  label: '❌ FALSE' },
  { value: 'PARTIALLY TRUE',         label: '⚠️ PARTIALLY TRUE' },
  { value: 'INSUFFICIENT EVIDENCE',  label: '🔍 INSUFFICIENT EVIDENCE' },
];

const STATUS_OPTIONS = [
  'VERIFIED',
  'NOT_FOUND',
  'CONTENT_MISMATCH',
  'PAYWALL_RESTRICTED',
  'ERROR',
];

export default function HITLPanel({ onResume }) {
  const { pendingReview, threadId, clearPendingReview } = useDebateStore();

  const [sourceOverrides, setSourceOverrides] = useState({});
  const [verdictOverride, setVerdictOverride] = useState('');
  const [submitting, setSubmitting]           = useState(false);
  const [error, setError]                     = useState(null);

  if (!pendingReview) return null;

  const sources = pendingReview.verification_results || [];
  const claim   = pendingReview.claim || '';

  const handleSourceChange = (url, newStatus) => {
    setSourceOverrides(prev => ({ ...prev, [url]: newStatus }));
  };

  const handleSubmit = async (skipOverrides = false) => {
    setSubmitting(true);
    setError(null);
    try {
      const body = skipOverrides
        ? { source_overrides: {}, verdict_override: null }
        : {
            source_overrides: sourceOverrides,
            verdict_override: verdictOverride || null,
          };

      const res = await fetch(`/api/debate/resume/${threadId}`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }

      const finalResult = await res.json();
      clearPendingReview();
      if (onResume) onResume(finalResult);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="hitl-panel animate-fade-up">
      {/* Header */}
      <div className="hitl-header">
        <div className="hitl-header-left">
          <span className="hitl-icon">✋</span>
          <div>
            <div className="hitl-title">Human review required</div>
            <div className="hitl-subtitle">
              Fact-check quality fell below threshold. Review sources and optionally override the verdict before the Moderator delivers its final call.
            </div>
          </div>
        </div>
        <span className="hitl-badge">HITL</span>
      </div>

      {/* Claim */}
      <div className="hitl-claim">
        <span className="hitl-claim-label">Claim under review</span>
        <span className="hitl-claim-text">"{claim}"</span>
      </div>

      {/* Source table */}
      {sources.length > 0 && (
        <div className="hitl-sources">
          <div className="hitl-section-label">Source overrides</div>
          <div className="hitl-source-table">
            <div className="hitl-source-row hitl-source-header">
              <span>URL</span>
              <span>Current status</span>
              <span>Your override</span>
            </div>
            {sources.map((src, i) => {
              const url      = src.url || '';
              const status   = src.status || 'UNKNOWN';
              const override = sourceOverrides[url];
              return (
                <div className="hitl-source-row" key={i}>
                  <span className="hitl-source-url" title={url}>
                    {url.length > 52 ? url.slice(0, 50) + '…' : url}
                  </span>
                  <span className={`hitl-status-badge hitl-status-${status.toLowerCase()}`}>
                    {status}
                  </span>
                  <select
                    className="hitl-select"
                    value={override || ''}
                    onChange={e => handleSourceChange(url, e.target.value)}
                  >
                    <option value="">No change</option>
                    {STATUS_OPTIONS.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Verdict override */}
      <div className="hitl-verdict-override">
        <div className="hitl-section-label">Verdict override (optional)</div>
        <select
          className="hitl-select hitl-verdict-select"
          value={verdictOverride}
          onChange={e => setVerdictOverride(e.target.value)}
        >
          {VERDICT_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <div className="hitl-verdict-hint">
          Leave blank to let the Moderator agent make the final decision.
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="hitl-error">⚠ {error}</div>
      )}

      {/* Actions */}
      <div className="hitl-actions">
        <button
          className="hitl-btn hitl-btn-primary"
          onClick={() => handleSubmit(false)}
          disabled={submitting}
        >
          {submitting
            ? <><span className="spinner" style={{ marginRight: 6 }} /> Resuming…</>
            : '⚖️ Submit review & resume'
          }
        </button>
        <button
          className="hitl-btn hitl-btn-ghost"
          onClick={() => handleSubmit(true)}
          disabled={submitting}
        >
          Skip — resume without changes
        </button>
      </div>
    </div>
  );
}
