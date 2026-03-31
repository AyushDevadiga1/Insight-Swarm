/**
 * BattleHeader.jsx — Agent VS banner at top of debate view
 * Shows 🛡️ ProAgent vs ⚔️ ConAgent with live pulse dots
 */

import React from 'react';
import { useDebateStore } from '../../store/useDebateStore';

export default function BattleHeader() {
  const { isRunning, activeStage } = useDebateStore();

  const proActive = isRunning && activeStage?.includes('pro');
  const conActive = isRunning && activeStage?.includes('con');

  return (
    <div className="battle-header">
      {/* ProAgent — left */}
      <div className="battle-agent">
        <div className="battle-agent-icon battle-icon-pro">🛡️</div>
        <div>
          <div className="battle-agent-name">ProAgent</div>
          <div className="battle-agent-role">defends the claim</div>
        </div>
        <div
          className="battle-pulse"
          style={{
            background: proActive ? 'var(--pro)' : 'var(--text-4)',
            animation: proActive ? 'pulse-glow 1.3s ease-in-out infinite' : 'none',
          }}
        />
      </div>

      <div className="battle-vs">VS</div>

      {/* ConAgent — right */}
      <div className="battle-agent battle-right">
        <div className="battle-agent-icon battle-icon-con">⚔️</div>
        <div>
          <div className="battle-agent-name">ConAgent</div>
          <div className="battle-agent-role">challenges the claim</div>
        </div>
        <div
          className="battle-pulse"
          style={{
            background: conActive ? 'var(--con)' : 'var(--text-4)',
            animation: conActive ? 'pulse-glow 1.3s ease-in-out infinite' : 'none',
          }}
        />
      </div>
    </div>
  );
}
