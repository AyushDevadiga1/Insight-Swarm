/**
 * ClaimInput.jsx — v3
 * Clean bottom input bar with send button and reset
 */

import React, { useRef } from 'react';
import { RefreshCw } from 'lucide-react';
import { useDebateStore } from '../../store/useDebateStore';
import { useApiStatusStore } from '../../store/useApiStatusStore';

const MIN_CHARS = 10;
const MAX_CHARS = 500;

export default function ClaimInput({ onVerify }) {
  const { claim, setClaim, isRunning, reset } = useDebateStore();
  const { hasPrimaryProvider } = useApiStatusStore();
  const textareaRef = useRef(null);

  const chars     = (claim || '').trim().length;
  const isReady   = chars >= MIN_CHARS && chars <= MAX_CHARS && !isRunning;
  const noProviders = !hasPrimaryProvider();

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && isReady) {
      onVerify();
    }
  };

  return (
    <div className="claim-input-wrap">
      <label className="claim-label">Subject claim</label>

      <div className="claim-textarea-wrap">
        <textarea
          ref={textareaRef}
          className="claim-textarea"
          value={claim}
          onChange={e => setClaim(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter a natural-language claim to verify…"
          disabled={isRunning}
          maxLength={MAX_CHARS}
          rows={2}
        />
        <button
          className="claim-send-btn"
          onClick={onVerify}
          disabled={!isReady || noProviders}
          title="Verify (Ctrl+Enter)"
        >
          {isRunning ? (
            <span className="spinner" />
          ) : (
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M2 21l21-9L2 3v7l15 2-15 2v7z" />
            </svg>
          )}
        </button>
      </div>

      {noProviders && (
        <div className="claim-no-providers">
          ⚠ No LLM providers available — check API health panel
        </div>
      )}

      <div className="claim-actions-row">
        <div className="claim-hint">
          {chars > 0 && chars < MIN_CHARS && (
            <span className="claim-hint-warn">{MIN_CHARS - chars} more chars needed</span>
          )}
          {chars >= MIN_CHARS && !isRunning && (
            <span className="claim-hint-ready">Ctrl+Enter to verify</span>
          )}
          {isRunning && (
            <span className="claim-hint-ready">Verification running…</span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className={`claim-char-count ${chars > MAX_CHARS - 20 ? 'claim-char-warn' : ''}`}>
            {chars}/{MAX_CHARS}
          </span>
          <button className="btn-reset" onClick={reset} title="Reset">
            <RefreshCw size={11} />
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}
