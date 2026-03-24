/**
 * DebateArena.jsx
 * 
 * The main debate display. Shows the live back-and-forth between ProAgent
 * and ConAgent, one round at a time, with round tab navigation.
 * 
 * During streaming: shows text as it arrives (throttled 80ms by useSSE).
 * After completion: shows the final stored arguments from result object.
 * 
 * CSS containment: `contain: strict` prevents the streaming text from
 * causing layout recalculation outside this container.
 */

import React, { useState, useEffect } from 'react';
import AgentBubble from './AgentBubble';
import { useDebateStore } from '../../store/useDebateStore';

export default function DebateArena({ result }) {
  const { isRunning, activeStage, agentMessages } = useDebateStore();
  const [activeRound, setActiveRound] = useState(1);

  // Determine how many rounds we have data for
  const rounds = result
    ? Math.min(
        (result.pro_arguments || []).length,
        (result.con_arguments || []).length
      )
    : Math.max(
        ...Object.keys(agentMessages)
          .filter(k => k.startsWith('PRO_') || k.startsWith('CON_'))
          .map(k => parseInt(k.split('_')[1], 10) || 0),
        0
      );

  // Auto-advance to the round currently being streamed
  useEffect(() => {
    if (!isRunning) return;
    const stage = activeStage || '';
    const match = stage.match(/round_(\d+)/);
    if (match) {
      setActiveRound(parseInt(match[1], 10));
    }
  }, [activeStage, isRunning]);

  if (!isRunning && rounds === 0) return null;

  // Determine which round to display
  const displayRound = Math.min(activeRound, Math.max(rounds, 1));

  // Get text for current round (live stream or final result)
  const proText = result
    ? (result.pro_arguments || [])[displayRound - 1]
    : agentMessages[`PRO_${displayRound}`];

  const conText = result
    ? (result.con_arguments || [])[displayRound - 1]
    : agentMessages[`CON_${displayRound}`];

  const proSources = result
    ? (result.pro_sources || [])[displayRound - 1] || []
    : [];

  const conSources = result
    ? (result.con_sources || [])[displayRound - 1] || []
    : [];

  // Is this specific agent/round actively streaming?
  const isProStreaming = isRunning && activeStage === `round_${displayRound}_pro`;
  const isConStreaming = isRunning && activeStage === `round_${displayRound}_con`;

  return (
    <div className="debate-arena">
      {/* Section label + round tabs */}
      <div className="debate-arena-header">
        <span className="section-label">Debate Log</span>
        <div className="round-tabs">
          {Array.from({ length: Math.max(rounds, isRunning ? displayRound : 0) }).map((_, i) => {
            const r = i + 1;
            const hasData = result
              ? !!((result.pro_arguments || [])[i])
              : !!(agentMessages[`PRO_${r}`] || agentMessages[`CON_${r}`]);

            return (
              <button
                key={r}
                className={`round-tab ${activeRound === r ? 'round-tab--active' : ''} ${!hasData ? 'round-tab--pending' : ''}`}
                onClick={() => setActiveRound(r)}
              >
                Rd {r}
                {isRunning && activeStage?.includes(`round_${r}`) && (
                  <span className="round-tab-live" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Debate content — CSS contained for performance */}
      <div className="debate-content">
        <AgentBubble
          agent="PRO"
          round={displayRound}
          text={proText}
          isStreaming={isProStreaming}
          sources={proSources}
        />
        <AgentBubble
          agent="CON"
          round={displayRound}
          text={conText}
          isStreaming={isConStreaming}
          sources={conSources}
        />
      </div>
    </div>
  );
}
