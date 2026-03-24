/**
 * FeedbackPanel.jsx
 */

import React, { useState } from 'react';
import { ThumbsUp, ThumbsDown, Check } from 'lucide-react';
import { submitFeedback } from '../../api/feedback';

export default function FeedbackPanel({ result }) {
  const [submitted, setSubmitted] = useState(null);

  const handle = async (val) => {
    const ok = await submitFeedback(result.claim, result.verdict, val);
    if (ok) setSubmitted(val);
  };

  if (submitted) {
    return (
      <div className="feedback-done">
        <Check size={14} />
        {submitted === 'UP' ? 'Marked accurate — thank you.' : 'Flagged for human review.'}
      </div>
    );
  }

  return (
    <div className="feedback-panel">
      <div className="section-label" style={{ marginBottom: '14px' }}>Feedback Protocol</div>
      <div className="feedback-btns">
        <button className="btn-feedback btn-feedback--up" onClick={() => handle('UP')}>
          <ThumbsUp size={14} /> Accurate
        </button>
        <button className="btn-feedback btn-feedback--down" onClick={() => handle('DOWN')}>
          <ThumbsDown size={14} /> Inaccurate
        </button>
      </div>
    </div>
  );
}
