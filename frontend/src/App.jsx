/**
 * App.jsx — Root component, fully revamped
 * 
 * What changed from old App.jsx:
 * - All state removed (lives in Zustand stores)
 * - setInterval fake timer GONE
 * - SSE hook drives real progress
 * - API health polling starts on mount
 * - Components import what they need from stores directly
 */

import React, { useState, useRef } from 'react';
import { useApiHealth } from './hooks/useApiHealth';
import { useSSE } from './hooks/useSSE';
import { useDebateStore } from './store/useDebateStore';

// Layout
import Sidebar from './components/layout/Sidebar';

// Input
import ClaimInput from './components/input/ClaimInput';

// Pipeline
import LiveTimeline from './components/pipeline/LiveTimeline';
import SubClaimBanner from './components/common/SubClaimBanner';

// Common
import ErrorBanner from './components/common/ErrorBanner';
import EmptyState from './components/common/EmptyState';
import AuroraBackground from './components/common/AuroraBackground';
import LoadingOrb from './components/common/LoadingOrb';

// Results
import VerdictCard from './components/results/VerdictCard';
import ReasoningPanel from './components/results/ReasoningPanel';
import MetricsGrid from './components/results/MetricsGrid';
import FallacyPanel from './components/results/FallacyPanel';
import SourceTable from './components/results/SourceTable';
import FeedbackPanel from './components/results/FeedbackPanel';

// Debate
import DebateArena from './components/debate/DebateArena';

export default function App() {
  const { claim, isRunning, result, error, sourceResults, agentMessages, setClaim, reset, history } = useDebateStore();

  // Start the /api/status polling on mount
  useApiHealth();

  // SSE trigger — a new UUID is generated each time the user clicks Verify.
  // useSSE reconnects only when runId changes, NOT on every re-render.
  // This is the fix for the requestAnimationFrame race condition.
  const [sseRunId, setSseRunId]   = useState('');
  const [sseClaim, setSseClaim]   = useState('');

  // Wire up SSE (hook manages connection lifecycle)
  useSSE(sseClaim, sseRunId);

  const handleVerify = () => {
    if (!claim.trim() || isRunning) return;
    // Each click generates a fresh UUID — this is the stable trigger
    // that useSSE listens to, avoiding the requestAnimationFrame race.
    const newRunId = crypto.randomUUID();
    setSseClaim(claim);
    setSseRunId(newRunId);
  };

  // Sources to show: live during streaming, from result after completion
  const displaySources = result?.verification_results ?? sourceResults;
  
  // Show the waiting state when it's running but nothing has streamed back yet
  const isWaiting = isRunning && Object.keys(agentMessages || {}).length === 0 && sourceResults.length === 0 && !result;

  return (
    <div className="app-shell">
      <AuroraBackground />
      <Sidebar
        onExampleClick={(ex) => setClaim(ex)}
        history={history}
      />

      <main className="main-content">
        <div className="main-inner">

          {/* Hero */}
          <div className="hero">
            <h1 className="hero-title">InsightSwarm</h1>
            <p className="hero-subtitle">Multi-Agent Truth Verification Protocol</p>
          </div>

          {/* Input */}
          <ClaimInput onVerify={handleVerify} />

          {/* Sub-claims (visible only if claim was decomposed) */}
          <SubClaimBanner />

          {/* Live pipeline timeline — shows during AND after run */}
          <LiveTimeline />

          {/* Error */}
          <ErrorBanner />

          {/* Empty state — only when nothing is happening */}
          {!isRunning && !result && !error && <EmptyState />}

          {/* Premium Waiting State (Loading Orb) */}
          {isWaiting && (
            <div className="waiting-state-container">
              <LoadingOrb message="Initializing Verification Protocol..." />
            </div>
          )}

          {/* Live debate — visible as soon as DECOMPOSING/SEARCHING stage arrives */}
          {(isRunning || sourceResults.length > 0 || result) && !isWaiting && (
            <DebateArena result={result} />
          )}

          {/* Final results — only after completion */}
          {result && (
            <div className="results-view">
              <VerdictCard result={result} />
              <ReasoningPanel result={result} />
              <MetricsGrid metrics={result.metrics} />
              <FallacyPanel result={result} />
              <SourceTable sources={displaySources} />
              <FeedbackPanel result={result} />
            </div>
          )}

          {/* Live sources during verification */}
          {isRunning && sourceResults.length > 0 && !result && (
            <SourceTable sources={sourceResults} />
          )}

          <footer className="app-footer">
            <span>InsightSwarm</span>
            <span>Groq + Gemini</span>
          </footer>

        </div>
      </main>
    </div>
  );
}
