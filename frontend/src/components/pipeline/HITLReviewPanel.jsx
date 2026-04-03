import React, { useState } from 'react';
import { useDebateStore } from '../../store/useDebateStore';

export default function HITLReviewPanel() {
  const { pendingReview, threadId, setResult, clearPendingReview, setError } = useDebateStore();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sourceOverrides, setSourceOverrides] = useState({});
  const [verdictOverride, setVerdictOverride] = useState('');

  if (!pendingReview) return null;

  const sources = pendingReview.verification_results || [];

  const handleSourceToggle = (url, currentStatus) => {
    setSourceOverrides(prev => ({
      ...prev,
      [url]: currentStatus === 'TRUE' ? 'FALSE' : 'TRUE'
    }));
  };

  const currentStatus = (url, origStatus) => sourceOverrides[url] || origStatus;

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const res = await fetch(`http://localhost:8000/api/debate/resume/${threadId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          source_overrides: sourceOverrides,
          verdict_override: verdictOverride || null
        })
      });

      if (!res.ok) {
        throw new Error("Failed to resume debate");
      }
      const data = await res.json();
      setResult(data);
      clearPendingReview();
    } catch (e) {
      console.error(e);
      setError({ type: 'SYSTEM_ERROR', message: e.message });
      clearPendingReview();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="hitl-overlay">
      <div className="hitl-modal animate-fade-up">
        <div className="hitl-header">
          <h2>
            <div className="hitl-pulse" />
            🧑 Human Review Required
          </h2>
          <p>The debate has paused for expert review. Please verify the source ratings below and click continue.</p>
        </div>

        <div className="hitl-body">
          <div className="hitl-section">
            <h3 className="hitl-section-title">Claim</h3>
            <p className="hitl-claim-text">"{pendingReview.claim}"</p>
          </div>

          <div className="hitl-section">
            <h3 className="hitl-section-title">Source Verification</h3>
            {sources.length === 0 ? (
              <p className="hitl-muted-text">No sources retrieved.</p>
            ) : (
              <div className="hitl-source-list">
                {sources.map((src, idx) => (
                  <div key={idx} className="hitl-source-item">
                    <div className="hitl-source-main">
                      <a href={src.url} target="_blank" rel="noreferrer" className="hitl-source-link">
                        {new URL(src.url).hostname}
                      </a>
                      <div className="hitl-source-snippet">{src.snippet}</div>
                      <div style={{ fontSize: '11px', color: '#64748b', marginTop: '6px' }}>
                        Agent: {src.agent_source} | Original: {src.status}
                      </div>
                    </div>
                    
                    <select
                      value={currentStatus(src.url, src.status)}
                      onChange={(e) => setSourceOverrides(prev => ({ ...prev, [src.url]: e.target.value }))}
                      className="hitl-select"
                      style={{ width: 'auto' }}
                    >
                      <option value="VERIFIED">✅ Verified</option>
                      <option value="NOT_FOUND">❌ Not Found</option>
                      <option value="CONTENT_MISMATCH">⚠️ Content Mismatch</option>
                      <option value="PAYWALL_RESTRICTED">🔒 Paywall</option>
                      <option value="INVALID_URL">🚫 Invalid URL</option>
                    </select>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="hitl-section">
            <h3 className="hitl-section-title">Final Verdict Override (Optional)</h3>
            <select
              value={verdictOverride}
              onChange={(e) => setVerdictOverride(e.target.value)}
              className="hitl-select"
            >
              <option value="">Let Moderator Decide</option>
              <option value="TRUE">Force TRUE</option>
              <option value="FALSE">Force FALSE</option>
              <option value="PARTIALLY TRUE">Force PARTIALLY TRUE</option>
              <option value="INSUFFICIENT EVIDENCE">Force INSUFFICIENT EVIDENCE</option>
            </select>
          </div>
        </div>

        <div className="hitl-footer">
          <button 
            className="hitl-submit-btn" 
            style={{ 
              background: 'linear-gradient(135deg, #10b981, #14b8a6)',
              color: '#fff',
              border: 'none',
              boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)'
            }} 
            onClick={handleSubmit} 
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Resuming...' : 'Continue Debate →'}
          </button>
          <button 
            className="hitl-submit-btn" 
            style={{ 
              background: 'transparent',
              color: 'var(--text-3)',
              border: '1px solid var(--border)',
              boxShadow: 'none',
              marginLeft: '12px'
            }} 
            onClick={clearPendingReview}
          >
            Skip Review
          </button>
        </div>
      </div>
    </div>
  );
}

