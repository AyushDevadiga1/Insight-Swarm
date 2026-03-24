/**
 * EmptyState.jsx
 */

import React from 'react';

export default function EmptyState() {
  return (
    <div className="empty-state">
      <div className="empty-glyph">◈</div>
      <h3 className="empty-heading">Ready to Verify</h3>
      <p className="empty-body">
        Type a claim and press <strong>Verify Claim</strong>.<br />
        Four AI agents debate, fact-check, and deliver a verdict.
      </p>
      <div className="empty-flow">
        {['Evidence Search', 'Debate (3 rounds)', 'Source Verification', 'Verdict'].map((step, i) => (
          <React.Fragment key={step}>
            <span className="empty-step">{step}</span>
            {i < 3 && <span className="empty-arrow">→</span>}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
