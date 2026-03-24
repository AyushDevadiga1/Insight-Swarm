/**
 * StageStep.jsx — Single row in the LiveTimeline
 */

import React from 'react';
import { STAGES } from '../../store/useDebateStore';

export default function StageStep({ step, isActive, isComplete }) {
  const meta = STAGES[step.stage] || { label: step.stage, icon: '•' };
  const elapsed = step.elapsed != null ? `+${step.elapsed}s` : '';

  return (
    <div className={`stage-step ${isActive ? 'stage-step--active' : ''} ${isComplete ? 'stage-step--complete' : ''}`}>
      {/* Left: icon */}
      <div className="stage-icon">
        {isComplete ? '✓' : isActive ? <span className="stage-pulse">{meta.icon}</span> : meta.icon}
      </div>

      {/* Middle: label + message */}
      <div className="stage-content">
        <span className="stage-label">{meta.label}</span>
        {step.message && step.message !== meta.label && (
          <span className="stage-message">{step.message}</span>
        )}
      </div>

      {/* Right: elapsed time */}
      {elapsed && <span className="stage-elapsed">{elapsed}</span>}
    </div>
  );
}
