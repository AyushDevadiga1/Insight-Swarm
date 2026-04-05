/**
 * HITLReviewPanel.jsx
 *
 * Human-In-The-Loop review overlay.
 *
 * Triggered when the SSE stream emits a `human_review_required` event.
 * The LangGraph backend has paused at the `human_review` node and is
 * waiting for a POST /api/debate/resume/{thread_id} call before continuing.
 *
 * What the reviewer can do:
 *  - Override any source verification status (VERIFIED / NOT_FOUND / ERROR)
 *  - Override the final verdict entirely
 *  - Skip review and let the moderator decide without changes
 *
 * On submit  → POST /api/debate/resume/{thread_id} with overrides
 * On skip    → POST /api/debate/resume/{thread_id} with empty overrides
 * After both → App switches to Verdict tab showing the final result
 */

import React, { useState, useCallback } from 'react';
import { useDebateStore } from '../../store/useDebateStore';

const VERDICT_OPTIONS = [
  'TRUE',
  'FALSE',
  'PARTIALLY TRUE',
  'INSUFFICIENT EVIDENCE',
];

const SOURCE_STATUS_OPTIONS = [
  'VERIFIED',
  'NOT_FOUND',
  'CONTENT_MISMATCH',
  'ERROR',
];

export default function HITLReviewPanel() {
  const { pendingReview, threadId, clearPendingReview, setResult, setError } =
    useDebateStore();

  const [sourceOverrides, setSourceOverrides] = useState({});
  const [verdictOverride, setVerdictOverride] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitLabel, setSubmitLabel] = useState('Submit review');

  // Not visible unless HITL is pending
  if (!pendingReview) return null;

  const verificationResults = pendingReview?.verification_results || [];

  const handleSourceChange = (url, newStatus) => {
    setSourceOverrides((prev) => ({ ...prev, [url]: newStatus }));
  };

  const submitReview = useCallback(
    async (skipOverrides = false) => {
      setSubmitting(true);
      setSubmitLabel(skipOverrides ? 'Resuming…' : 'Submitting…');

      const payload = {
        source_overrides: skipOverrides ? {} : sourceOverrides,
        verdict_override: skipOverrides ? null : verdictOverride || null,
      };

      try {
        const res = await fetch(`/api/debate/resume/${threadId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }

        const finalResult = await res.json();
        clearPendingReview();
        setResult(finalResult);
      } catch (e) {
        setError({ type: 'SYSTEM_ERROR', message: `Resume failed: ${e.message}` });
        clearPendingReview();
      } finally {
        setSubmitting(false);
        setSubmitLabel('Submit review');
      }
    },
    [sourceOverrides, verdictOverride, threadId, clearPendingReview, setResult, setError]
  );

  return (
    /* Full-screen semi-opaque overlay — does NOT use position:fixed
       Instead it sits in normal flow inside app-shell as a full-height flex child */
    <div className="hitl-overlay">
      <div className="hitl-panel">

        {/* Header */}
        <div className="hitl-header">
          <div className="hitl-header-left">
            <div className="hitl-icon">✋</div>
            <div>
              <div className="hitl-title">Human review requested</div>
              <div className="hitl-subtitle">
                The pipeline has paused before the final verdict.
                Review the source verifications and optionally override the outcome.
              </div>
            </div>
          </div>
          <div className="hitl-thread-id">
            thread: {threadId?.slice(0, 8)}…
          </div>
        </div>

        {/* Claim */}
        {pendingReview?.claim && (
          <div className="hitl-claim-row">
            <span className="hitl-claim-label">Claim</span>
            <span className="hitl-claim-text">"{pendingReview.claim}"</span>
          </div>
        )}

        {/* Source verification table */}
        {verificationResults.length > 0 && (
          <div className="hitl-section">
            <div className="hitl-section-label">
              Source verifications
              <span className="hitl-section-hint">
                — override any status that looks wrong
              </span>
            </div>
            <div className="hitl-sources-table">
              {verificationResults.map((src, i) => {
                const url = src.url || '';
                const current =
                  sourceOverrides[url] || src.status || 'UNKNOWN';
                const isOverridden = !!sourceOverrides[url];

                return (
                  <div className="hitl-source-row" key={i}>
                    <span className="hitl-src-num">
                      {String(i + 1).padStart(2, '0')}
                    </span>

                    <div className="hitl-src-url-wrap">
                      <span className="hitl-src-url" title={url}>
                        {url.length > 60 ? url.slice(0, 58) + '…' : url}
                      </span>
                      {src.content_preview && (
                        <span className="hitl-src-preview">
                          {src.content_preview.slice(0, 80)}…
                        </span>
                      )}
                    </div>

                    <select
                      className={`hitl-src-select ${
                        isOverridden ? 'hitl-src-select-overridden' : ''
                      }`}
                      value={current}
                      onChange={(e) => handleSourceChange(url, e.target.value)}
                    >
                      {SOURCE_STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>

                    {isOverridden && (
                      <span className="hitl-override-badge">overridden</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Verdict override */}
        <div className="hitl-section">
          <div className="hitl-section-label">
            Verdict override
            <span className="hitl-section-hint">
              — optional, leave blank to let the moderator decide
            </span>
          </div>
          <div className="hitl-verdict-options">
            {VERDICT_OPTIONS.map((v) => (
              <button
                key={v}
                className={`hitl-verdict-btn ${
                  verdictOverride === v ? 'hitl-verdict-btn-selected' : ''
                }`}
                onClick={() =>
                  setVerdictOverride((prev) => (prev === v ? '' : v))
                }
              >
                {v}
              </button>
            ))}
          </div>
          {verdictOverride && (
            <div className="hitl-verdict-selected-label">
              Override set to:{' '}
              <span className="hitl-verdict-selected-value">
                {verdictOverride}
              </span>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="hitl-actions">
          <button
            className="hitl-btn-submit"
            onClick={() => submitReview(false)}
            disabled={submitting}
          >
            {submitting && submitLabel === 'Submitting…' ? (
              <span className="hitl-spinner" />
            ) : null}
            {submitLabel === 'Submitting…' ? 'Submitting…' : 'Submit review'}
          </button>

          <button
            className="hitl-btn-skip"
            onClick={() => submitReview(true)}
            disabled={submitting}
          >
            {submitting && submitLabel === 'Resuming…' ? (
              <span className="hitl-spinner" />
            ) : null}
            {submitLabel === 'Resuming…' ? 'Resuming…' : 'Skip — let moderator decide'}
          </button>
        </div>

      </div>
    </div>
  );
}
