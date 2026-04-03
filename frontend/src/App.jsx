/**
 * App.jsx — v3 redesign
 * 3-panel shell: Sidebar | Main (Home/Debate/Verdict) | StagePanel
 */

import React, { useState, useRef } from 'react';
import { useApiHealth } from './hooks/useApiHealth';
import { useSSE } from './hooks/useSSE';
import { useDebateStore } from './store/useDebateStore';

// Layout
import Sidebar from './components/layout/Sidebar';
import StagePanel from './components/pipeline/StagePanel';

// Views
import WelcomeScreen from './components/common/WelcomeScreen';
import BattleHeader from './components/debate/BattleHeader';
import DebateArena from './components/debate/DebateArena';
import ClaimInput from './components/input/ClaimInput';

// Common
import ErrorBanner from './components/common/ErrorBanner';
import SubClaimBanner from './components/common/SubClaimBanner';
import HITLReviewPanel from './components/pipeline/HITLReviewPanel';

// Results
import VerdictCard from './components/results/VerdictCard';
import ReasoningPanel from './components/results/ReasoningPanel';
import MetricsGrid from './components/results/MetricsGrid';
import FallacyPanel from './components/results/FallacyPanel';
import SourceTable from './components/results/SourceTable';
import FeedbackPanel from './components/results/FeedbackPanel';

export default function App() {
  const {
    claim, isRunning, result, error,
    sourceResults, agentMessages, setClaim, reset, history,
  } = useDebateStore();

  // Active tab: 'home' | 'debate' | 'verdict'
  const [activeTab, setActiveTab] = useState('home');

  // SSE trigger
  const [sseRunId, setSseRunId] = useState('');
  const [sseClaim, setSseClaim] = useState('');

  useApiHealth();
  useSSE(sseClaim, sseRunId);

  const handleVerify = () => {
    if (!claim.trim() || isRunning) return;
    const newRunId = crypto.randomUUID();
    setSseClaim(claim);
    setSseRunId(newRunId);
    setActiveTab('debate');
  };

  // Auto-switch to verdict tab when result arrives
  React.useEffect(() => {
    if (result && !isRunning) {
      setActiveTab('verdict');
    }
  }, [result, isRunning]);

  const displaySources = result?.verification_results ?? sourceResults;

  const tabs = [
    { id: 'home',    label: 'Home' },
    { id: 'debate',  label: 'Debate' },
    { id: 'verdict', label: 'Verdict', disabled: !result && !isRunning },
  ];

  return (
    <div className="app-shell">
      <Sidebar
        onExampleClick={(ex) => { setClaim(ex); setActiveTab('debate'); }}
        history={history}
      />

      <div className="main-content">
        {/* Nav tabs */}
        <nav className="main-nav">
          {tabs.map(tab => (
            <div
              key={tab.id}
              className={`nav-tab ${activeTab === tab.id ? 'active' : ''} ${tab.disabled ? 'disabled' : ''}`}
              onClick={() => !tab.disabled && setActiveTab(tab.id)}
              style={tab.disabled ? { opacity: 0.35, cursor: 'default' } : {}}
            >
              {tab.label}
            </div>
          ))}
        </nav>

        {/* Content row */}
        <div className="content-row">
          <div className="debate-col">

            {/* ── HOME ── */}
            {activeTab === 'home' && (
              <WelcomeScreen onStart={() => setActiveTab('debate')} />
            )}

            {/* ── DEBATE ── */}
            {activeTab === 'debate' && (
              <>
                <BattleHeader />
                {claim && (
                  <div className="claim-pill">
                    <span className="claim-pill-label">Claim</span>
                    <span className="claim-pill-text">"{claim}"</span>
                  </div>
                )}
                <SubClaimBanner />
                <ErrorBanner />
                <DebateArena result={isRunning ? null : result} />
                <ClaimInput onVerify={handleVerify} />
              </>
            )}

            {/* ── VERDICT ── */}
            {activeTab === 'verdict' && (
              <div className="verdict-section animate-fade-up">
                {result ? (
                  <>
                    <div className="verdict-mod-header">
                      <div className="verdict-mod-avatar">⚖️</div>
                      <span className="verdict-mod-label">Moderator · final analysis</span>
                    </div>
                    <VerdictCard result={result} />
                    <ReasoningPanel result={result} />
                    <MetricsGrid metrics={result.metrics} />
                    <FallacyPanel result={result} />
                    <SourceTable sources={displaySources} />
                    <FeedbackPanel result={result} />
                    <footer className="app-footer">
                      <span>InsightSwarm</span>
                      <span>Multi-Agent Verification</span>
                    </footer>
                  </>
                ) : (
                  <div style={{ color: 'var(--text-3)', fontSize: '13px', marginTop: '40px' }}>
                    No verdict yet — run a verification first.
                  </div>
                )}
              </div>
            )}

          </div>

          {/* Right stage panel — always visible */}
          <StagePanel />
        </div>
      </div>
      
      {/* Human In The Loop Overlay */}
      <HITLReviewPanel />
    </div>
  );
}
