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

import React, { useState } from 'react';
import { useApiHealth } from './hooks/useApiHealth';
import { useSSE } from './hooks/useSSE';
import { useDebateStore } from './store/useDebateStore';

// Layout
import Sidebar from './components/layout/Sidebar';

// Input
import ClaimInput from './components/input/ClaimInput';

// Pipeline
import LiveTimeline from './components/pipeline/LiveTimeline';

// Common
import ErrorBanner from './components/common/ErrorBanner';
import EmptyState from './components/common/EmptyState';

// Results
import VerdictCard from './components/results/VerdictCard';
import ReasoningPanel from './components/results/ReasoningPanel';
import MetricsGrid from './components/results/MetricsGrid';
import SourceTable from './components/results/SourceTable';
import FeedbackPanel from './components/results/FeedbackPanel';

// Debate
import DebateArena from './components/debate/DebateArena';

export default function App() {
  const { claim, isRunning, result, error, sourceResults, setClaim, reset, history } = useDebateStore();

  // Start the /api/status polling on mount
  useApiHealth();

  // SSE trigger state — when this is true, useSSE opens the connection
  const [sseEnabled, setSseEnabled] = useState(false);
  const [sseClaim, setSseClaim] = useState('');

  // Wire up SSE (hook manages connection lifecycle)
  useSSE(sseClaim, sseEnabled);

  const handleVerify = () => {
    if (!claim.trim() || isRunning) return;
    setSseClaim(claim);
    setSseEnabled(true);
    // After SSE hook picks up the new claim+enabled, we reset sseEnabled
    // so it doesn't reconnect on re-renders. The hook's useEffect deps
    // [enabled, claim] mean it only reconnects when these values change.
    requestAnimationFrame(() => setSseEnabled(false));
  };

  // Sources to show: live during streaming, from result after completion
  const displaySources = result?.verification_results ?? sourceResults;

  return (
    <div className="app-shell">
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

          {/* Live pipeline timeline — shows during AND after run */}
          <LiveTimeline />

          {/* Error */}
          <ErrorBanner />

          {/* Empty state — only when nothing is happening */}
          {!isRunning && !result && !error && <EmptyState />}

          {/* Live debate — visible during streaming */}
          {(isRunning || result) && (
            <DebateArena result={result} />
          )}

          {/* Final results — only after completion */}
          {result && (
            <div className="results-view">
              <VerdictCard result={result} />
              <ReasoningPanel result={result} />
              <MetricsGrid metrics={result.metrics} />
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
