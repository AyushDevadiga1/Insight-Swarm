/**
 * ClaimInput.jsx — Revamped textarea with char counter and ready state
 */

import React, { useRef } from 'react';
import { RefreshCw, Send } from 'lucide-react';
import { useDebateStore } from '../../store/useDebateStore';
import { useApiStatusStore } from '../../store/useApiStatusStore';

const MIN_CHARS = 10;
const MAX_CHARS = 500;

export default function ClaimInput({ onVerify }) {
  const { claim, setClaim, isRunning, reset } = useDebateStore();
  const { hasPrimaryProvider } = useApiStatusStore();
  const textareaRef = useRef(null);

  const chars = (claim || '').trim().length;
  const isReady = chars >= MIN_CHARS && chars <= MAX_CHARS && !isRunning;
  const noProviders = !hasPrimaryProvider();

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && isReady) {
      onVerify();
    }
  };

  return (
    <div className="claim-input-wrap">
      <label className="claim-label">Subject Claim</label>

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
          rows={3}
        />
        <div className={`claim-char-count ${chars > MAX_CHARS - 20 ? 'claim-char-warn' : ''}`}>
          {chars} / {MAX_CHARS}
        </div>
      </div>

      {noProviders && (
        <div className="claim-no-providers">
          ⚠ No LLM providers available — check API status panel
        </div>
      )}

      <div className="claim-actions">
        <button
          className={`btn-verify ${isReady && !noProviders ? 'btn-verify--ready' : 'btn-verify--disabled'}`}
          onClick={onVerify}
          disabled={!isReady || noProviders}
        >
          {isRunning ? (
            <span className="btn-verify-running">
              <span className="spinner" />
              Verifying…
            </span>
          ) : (
            <>
              <Send size={14} />
              Verify Claim
            </>
          )}
        </button>

        <button className="btn-reset" onClick={reset} title="Reset">
          <RefreshCw size={16} />
        </button>
      </div>

      <div className="claim-hint">
        {chars > 0 && chars < MIN_CHARS && (
          <span className="hint-warn">{MIN_CHARS - chars} more characters needed</span>
        )}
        {chars >= MIN_CHARS && (
          <span className="hint-ready">↵ Ctrl+Enter to verify</span>
        )}
      </div>
    </div>
  );
}
