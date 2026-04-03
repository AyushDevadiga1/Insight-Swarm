/**
 * StagePanel.jsx — Grok-style right-side pipeline timeline
 * Vertical dot-and-line layout with live stage tracking from SSE store.
 */

import React, { useState, useEffect } from 'react';
import { useDebateStore, STAGES } from '../../store/useDebateStore';

const PIPELINE_STEPS = [
  { key: 'decomposing',   label: 'Decompose',      sub: 'claim analysis' },
  { key: 'searching',     label: 'Evidence search', sub: 'web sources' },
  { key: 'round_1_pro',   label: 'Pro · round 1',  sub: 'supporting' },
  { key: 'round_1_con',   label: 'Con · round 1',  sub: 'rebuttal' },
  { key: 'round_2_pro',   label: 'Pro · round 2',  sub: 'supporting' },
  { key: 'round_2_con',   label: 'Con · round 2',  sub: 'rebuttal' },
  { key: 'round_3_pro',   label: 'Pro · round 3',  sub: 'supporting' },
  { key: 'round_3_con',   label: 'Con · round 3',  sub: 'rebuttal' },
  { key: 'fact_checking', label: 'Fact check',      sub: 'source verification' },
  { key: 'human_review',  label: 'Human Review',    sub: 'intervention pause' },
  { key: 'moderating',    label: 'Moderator',       sub: 'synthesis' },
  { key: 'complete',      label: 'Verdict',         sub: 'complete' },
];

function getStepStatus(stepKey, activeStage, stageHistory) {
  if (stepKey === activeStage) return 'active';
  const reached = stageHistory.some(s => s.stage === stepKey);
  if (reached) return 'done';
  // Check if active stage is further ahead
  const activeIdx = PIPELINE_STEPS.findIndex(s => s.key === activeStage);
  const stepIdx   = PIPELINE_STEPS.findIndex(s => s.key === stepKey);
  if (activeIdx > stepIdx && stepIdx >= 0) return 'done';
  return 'pending';
}

export default function StagePanel() {
  const { isRunning, activeStage, stageHistory, result } = useDebateStore();
  const [elapsed, setElapsed] = useState(0);
  const [startTime] = useState(Date.now());

  useEffect(() => {
    if (!isRunning) { setElapsed(0); return; }
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [isRunning]);

  const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  // Only show steps that are relevant (hide round 3 if not reached)
  const visibleSteps = PIPELINE_STEPS.filter(step => {
    if (!step.key.includes('round_3')) return true;
    return stageHistory.some(s => s.key?.includes('round_3')) || activeStage?.includes('round_3');
  });

  return (
    <div className="stage-panel">
      <div className="stage-panel-title">
        {isRunning ? `Pipeline · ${fmt(elapsed)}` : 'Pipeline'}
      </div>

      <div className="stage-list">
        {visibleSteps.map((step, i) => {
          const status = result
            ? (step.key === 'complete' ? 'done' : 'done')
            : getStepStatus(step.key, activeStage, stageHistory);

          const stageEntry = stageHistory.find(s => s.stage === step.key);

          return (
            <div className="stage-step" key={step.key}>
              <div className="stage-dot-wrap">
                <div className={`stage-dot ${status}`} />
              </div>
              <div className="stage-info">
                <div className={`stage-label ${status}`}>{step.label}</div>
                {status === 'done' && stageEntry?.elapsed && (
                  <div className="stage-tick">✓ {stageEntry.elapsed}</div>
                )}
                {status === 'done' && !stageEntry?.elapsed && (
                  <div className="stage-tick">✓ done</div>
                )}
                {status === 'active' && (
                  <div className="stage-elapsed">{fmt(elapsed)}</div>
                )}
                {status === 'pending' && (
                  <div className="stage-sublabel">{step.sub}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
