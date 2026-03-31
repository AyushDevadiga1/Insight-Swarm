import React from 'react';

export default function WelcomeScreen({ onStart }) {
  return (
    <div className="welcome-screen">
      <div className="welcome-badge">
        <div className="welcome-badge-dot" />
        <span className="welcome-badge-text">4 agents · live debate · real sources</span>
      </div>

      <h1 className="welcome-title">Truth by debate</h1>

      <p className="welcome-subtitle">
        Submit any claim. Four specialised AI agents argue, challenge,
        fact-check, and converge on a verified verdict — showing their
        full reasoning every step of the way.
      </p>

      {/* VS matchup */}
      <div className="welcome-matchup">
        <div className="welcome-agent-card">
          <span className="welcome-agent-icon">🛡️</span>
          <span className="welcome-agent-name">ProAgent</span>
          <span className="welcome-agent-role">defends true</span>
        </div>

        <div className="welcome-vs-divider">
          <span className="welcome-vs-text">VS</span>
        </div>

        <div className="welcome-agent-card">
          <span className="welcome-agent-icon">⚔️</span>
          <span className="welcome-agent-name">ConAgent</span>
          <span className="welcome-agent-role">attacks claim</span>
        </div>

        <div className="welcome-col-divider" />

        <div className="welcome-agent-card">
          <span className="welcome-agent-icon">🔬</span>
          <span className="welcome-agent-name">FactChecker</span>
          <span className="welcome-agent-role">verifies sources</span>
        </div>

        <div className="welcome-agent-card">
          <span className="welcome-agent-icon">⚖️</span>
          <span className="welcome-agent-name">Moderator</span>
          <span className="welcome-agent-role">delivers verdict</span>
        </div>
      </div>

      {/* Stats */}
      <div className="welcome-stats">
        <div className="welcome-stat">
          <div className="welcome-stat-num">3</div>
          <div className="welcome-stat-label">debate rounds</div>
        </div>
        <div className="welcome-stat">
          <div className="welcome-stat-num">5+</div>
          <div className="welcome-stat-label">sources checked</div>
        </div>
        <div className="welcome-stat">
          <div className="welcome-stat-num">~30s</div>
          <div className="welcome-stat-label">avg runtime</div>
        </div>
        <div className="welcome-stat">
          <div className="welcome-stat-num">100%</div>
          <div className="welcome-stat-label">reasoning shown</div>
        </div>
      </div>

      <button className="welcome-cta" onClick={onStart}>
        Start a debate →
      </button>
    </div>
  );
}
