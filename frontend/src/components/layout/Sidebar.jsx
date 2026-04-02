/**
 * Sidebar.jsx — v3
 * Brand | API health bars | Agent list with symbols | Examples | History
 */

import React, { useState } from 'react';
import ApiStatusPanel from '../status/ApiStatusPanel';
import { useDebateStore } from '../../store/useDebateStore';

const AGENTS = [
  { key: 'pro',  icon: '🛡️', name: 'ProAgent',    role: 'defends claim is true',    iconClass: 'agent-icon-pro',  color: 'var(--pro)'  },
  { key: 'con',  icon: '⚔️', name: 'ConAgent',    role: 'challenges the claim',      iconClass: 'agent-icon-con',  color: 'var(--con)'  },
  { key: 'fact', icon: '🔬', name: 'FactChecker', role: 'verifies sources & URLs',   iconClass: 'agent-icon-fact', color: 'var(--fact)' },
  { key: 'mod',  icon: '⚖️', name: 'Moderator',   role: 'synthesises final verdict', iconClass: 'agent-icon-mod',  color: 'var(--mod)'  },
];

const EXAMPLES = [
  'Coffee prevents cancer',
  'Exercise improves mental health',
  'The Earth is flat',
  'Vaccines cause autism',
  'AI will replace all jobs by 2030',
];

export default function Sidebar({ onExampleClick, history = [] }) {
  const { activeStage, isRunning, result } = useDebateStore();

  const substitutions = result?.metrics?.model_substitutions || [];

  const getAgentPulseColor = (key) => {
    if (!isRunning) return 'var(--text-4)';
    if (key === 'pro'  && activeStage?.includes('pro'))  return 'var(--pro)';
    if (key === 'con'  && activeStage?.includes('con'))  return 'var(--con)';
    if (key === 'fact' && activeStage?.includes('fact')) return 'var(--fact)';
    if (key === 'mod'  && activeStage?.includes('mod'))  return 'var(--mod)';
    return 'var(--text-4)';
  };

  const isAgentActive = (key) => {
    if (!isRunning) return false;
    return (
      (key === 'pro'  && activeStage?.includes('pro'))  ||
      (key === 'con'  && activeStage?.includes('con'))  ||
      (key === 'fact' && activeStage?.includes('fact')) ||
      (key === 'mod'  && activeStage?.includes('mod'))
    );
  };

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <div className="sidebar-brand-name">InsightSwarm</div>
        <div className="sidebar-brand-tag">multi-agent truth verification</div>
      </div>

      {/* API Health */}
      <ApiStatusPanel />

      {/* Model Substitutions Warning */}
      {substitutions.length > 0 && (
        <div className="sidebar-section" style={{ marginTop: '-10px' }}>
          <div className="claim-no-providers" style={{ display: 'flex', gap: '6px', alignItems: 'flex-start' }}>
            <span>⚠</span>
            <span>Rate limit hit — switched to fallback provider</span>
          </div>
        </div>
      )}

      {/* Agents */}

      <div className="sidebar-section">
        <div className="sidebar-section-label">Agents</div>
        <div className="agent-list">
          {AGENTS.map(agent => (
            <div className="agent-row" key={agent.key}>
              <div className={`agent-icon ${agent.iconClass}`}>
                {agent.icon}
              </div>
              <div className="agent-info">
                <div className="agent-name">{agent.name}</div>
                <div className="agent-role">{agent.role}</div>
              </div>
              <div
                className={`agent-pulse ${isAgentActive(agent.key) ? 'agent-pulse-active' : ''}`}
                style={{ background: getAgentPulseColor(agent.key) }}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Examples */}
      <div className="sidebar-section">
        <div className="sidebar-section-label">Try these</div>
        <div className="example-list">
          {EXAMPLES.map(ex => (
            <button
              key={ex}
              className="example-btn"
              onClick={() => onExampleClick(ex)}
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Session history */}
      {history.length > 0 && (
        <div className="sidebar-section">
          <div className="sidebar-section-label">History</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
            {history.slice(0, 6).map((item, i) => {
              const isTrue    = item.verdict?.includes('TRUE') && !item.verdict?.includes('PARTIAL');
              const isFalse   = item.verdict?.includes('FALSE');
              const vColor    = isTrue ? 'var(--pro)' : isFalse ? 'var(--con)' : 'var(--mod)';
              return (
                <div
                  key={i}
                  style={{
                    padding: '7px 8px',
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)',
                  }}
                >
                  <div style={{ fontSize: '11px', color: 'var(--text-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginBottom: '3px' }}>
                    {item.claim}
                  </div>
                  <span style={{
                    fontFamily: 'var(--mono)',
                    fontSize: '9px',
                    padding: '1px 6px',
                    border: `1px solid ${vColor}`,
                    borderRadius: '20px',
                    color: vColor,
                    letterSpacing: '0.04em',
                  }}>
                    {item.verdict}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="sidebar-footer">Multi-agent · live debate</div>
    </aside>
  );
}
