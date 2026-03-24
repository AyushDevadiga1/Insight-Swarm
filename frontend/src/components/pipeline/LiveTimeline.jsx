/**
 * LiveTimeline.jsx
 * 
 * Replaces the fake setInterval PipelineProgress.
 * Renders real stage events from the SSE stream stored in useDebateStore.stageHistory.
 * 
 * Each row shows:
 *   icon  elapsed  stage-label  message  [pulsing if active]
 * 
 * Performance:
 * - `contain: layout style` on the container: adding new rows doesn't
 *   trigger layout recalc for anything outside this element
 * - Only the last 12 stages are rendered (older ones are still in state)
 */

import React, { useRef, useEffect } from 'react';
import { useDebateStore, STAGES } from '../../store/useDebateStore';
import StageStep from './StageStep';

export default function LiveTimeline() {
  const { isRunning, stageHistory, activeStage, result, error } = useDebateStore();
  const bottomRef = useRef(null);

  // Auto-scroll to the latest stage
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [stageHistory.length]);

  // Don't render if nothing has happened yet
  if (!isRunning && stageHistory.length === 0 && !result && !error) return null;

  const visibleStages = stageHistory.slice(-12);
  const overallPct = STAGES[activeStage]?.pct ?? 0;

  return (
    <div className="timeline-wrap">
      {/* Overall progress bar */}
      <div className="timeline-progress-track">
        <div
          className="timeline-progress-fill"
          style={{ width: `${Math.round(overallPct * 100)}%` }}
        />
      </div>

      {/* Stage list */}
      <div className="timeline-stage-list">
        {visibleStages.map((step, i) => {
          const isActive = step.stage === activeStage && isRunning;
          const isComplete = !isActive && i < visibleStages.length - 1;
          return (
            <StageStep
              key={`${step.stage}-${step.timestamp}`}
              step={step}
              isActive={isActive}
              isComplete={isComplete}
            />
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
