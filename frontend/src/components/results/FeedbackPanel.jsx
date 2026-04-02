/**
 * FeedbackPanel.jsx — v3
 * Self-contained with local state to avoid store coupling issues.
 */

import React, { useState } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { submitFeedback } from '../../api';

export default function FeedbackPanel({ result }) {
  const [given, setGiven] = useState(null);

  if (!result) return null;

  const handleFeedback = async (value) => {
    await submitFeedback(result.claim, result.verdict, value);
    setGiven(value);
  };

  if (given) {
    const msg = given === 'UP'
      ? '✓ Marked as accurate — thank you.'
      : '✗ Flagged for review — thank you.';
    return (
      <div className="feedback-panel">
        <div className="feedback-done">{msg}</div>
      </div>
    );
  }

  return (
    <div className="feedback-panel">
      <div className="feedback-label">Was this verdict accurate?</div>
      <div className="feedback-btns">
        <button className="btn-feedback btn-feedback-up" onClick={() => handleFeedback('UP')}>
          <ThumbsUp size={13} />
          Accurate
        </button>
        <button className="btn-feedback btn-feedback-down" onClick={() => handleFeedback('DOWN')}>
          <ThumbsDown size={13} />
          Inaccurate
        </button>
      </div>
    </div>
  );
}
