/**
 * Sidebar.jsx — Revamped sidebar with live API status at the top
 */

import React, { useState } from 'react';
import { Shield, Zap, Search, Scale, ChevronDown, ChevronUp } from 'lucide-react';
import ApiStatusPanel from '../status/ApiStatusPanel';

const AGENTS = [
  { name: 'ProAgent',    num: '01', desc: 'Argues claim is TRUE using sources',    color: 'var(--pro)',  icon: Shield },
  { name: 'ConAgent',    num: '02', desc: 'Adversarial rebuttal, finds flaws',     color: 'var(--con)',  icon: Zap },
  { name: 'FactChecker', num: '03', desc: 'Verifies URLs, detects hallucinations', color: 'var(--fact)', icon: Search },
  { name: 'Moderator',   num: '04', desc: 'Synthesizes verdict, scores quality',   color: 'var(--mod)',  icon: Scale },
];

const EXAMPLES = [
  'Coffee prevents cancer',
  'Exercise improves mental health',
  'The Earth is flat',
  'Vaccines cause autism',
  'AI will replace all jobs by 2030',
];

export default function Sidebar({ onExampleClick, history = [] }) {
  const [agentsExpanded, setAgentsExpanded] = useState(true);

  return (
    <aside className="sidebar">
      {/* Live API Status — always visible at top */}
      <ApiStatusPanel />

      <div className="sidebar-divider" />

      {/* Agent Architecture — collapsible */}
      <div className="sidebar-section">
        <button
          className="sidebar-section-header"
          onClick={() => setAgentsExpanded(v => !v)}
        >
          <span className="panel-label">Agent Architecture</span>
          {agentsExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>

        {agentsExpanded && (
          <div className="agent-list">
            {AGENTS.map(({ name, num, desc, color, icon: Icon }) => (
              <div className="agent-row" key={name}>
                <div className="agent-row-top">
                  <span className="agent-num">{num}</span>
                  <div className="agent-icon" style={{ color }}>
                    <Icon size={12} />
                  </div>
                  <span className="agent-name" style={{ color }}>{name}</span>
                </div>
                <p className="agent-desc">{desc}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="sidebar-divider" />

      {/* Example Claims */}
      <div className="sidebar-section">
        <div className="panel-label" style={{ marginBottom: '10px' }}>Example Claims</div>
        <div className="example-list">
          {EXAMPLES.map(ex => (
            <button key={ex} className="example-btn" onClick={() => onExampleClick(ex)}>
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Session History */}
      {history.length > 0 && (
        <>
          <div className="sidebar-divider" />
          <div className="sidebar-section sidebar-history">
            <div className="panel-label" style={{ marginBottom: '10px' }}>Session History</div>
            <div className="history-list">
              {history.map((item, i) => {
                const isTrue = item.verdict?.includes('TRUE') && !item.verdict?.includes('PARTIAL');
                const isFalse = item.verdict?.includes('FALSE');
                const vColor = isTrue ? 'var(--pro)' : isFalse ? 'var(--con)' : 'var(--mod)';
                return (
                  <div className="history-item" key={i}>
                    <p className="history-claim">{item.claim}</p>
                    <span className="history-verdict" style={{ color: vColor, borderColor: vColor }}>
                      {item.verdict}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* Footer */}
      <div className="sidebar-footer">
        POWERED BY<br />
        <span className="sidebar-footer-bold">GROQ + GEMINI</span>
      </div>
    </aside>
  );
}
