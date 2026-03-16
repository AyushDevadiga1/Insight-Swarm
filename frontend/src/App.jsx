import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import HeroHeader from './components/HeroHeader';
import ClaimInput from './components/ClaimInput';
import PipelineProgress from './components/PipelineProgress';
import EmptyState from './components/EmptyState';
import VerdictCard from './components/VerdictCard';
import DebateLog from './components/DebateLog';
import SourceTable from './components/SourceTable';
import MetricsBar from './components/MetricsBar';
import FeedbackPanel from './components/FeedbackPanel';
import ApiError from './components/ApiError';
import BotBubble from './components/BotBubble';
import { verifyClaim } from './api';

function App() {
  const [claim, setClaim] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeStage, setActiveStage] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    let timer;
    if (loading && activeStage < 4) {
      timer = setInterval(() => {
        setActiveStage(prev => prev + 1);
      }, 4000);
    }
    return () => clearInterval(timer);
  }, [loading, activeStage]);

  const handleVerify = async () => {
    setLoading(true);
    setResult(null);
    setError(null);
    setActiveStage(1);

    try {
      const data = await verifyClaim(claim);
      setResult(data);
      setHistory(prev => [{ claim: data.claim, verdict: data.verdict }, ...prev].slice(0, 10));
      setActiveStage(5);
    } catch (err) {
      setError(err);
      setActiveStage(0);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setClaim('');
    setResult(null);
    setError(null);
    setLoading(false);
    setActiveStage(0);
  };

  const handleExample = (ex) => {
    setClaim(ex);
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar onExampleClick={handleExample} history={history} />
      
      <main className="flex-1 overflow-y-auto bg-bg p-12 flex flex-col items-center">
        <div className="w-full max-w-4xl flex flex-col items-center">
          <div className="w-full text-left">
            <HeroHeader />
          </div>
          
          <ClaimInput 
            value={claim} 
            onChange={setClaim} 
            onVerify={handleVerify} 
            onReset={reset}
            loading={loading}
          />

          <PipelineProgress active={activeStage} />

          {error && <ApiError error={error} />}

          {!loading && !result && !error && (
            <EmptyState />
          )}

          {result && (
            <div className="w-full animate-fade-in flex flex-col items-center">
              <VerdictCard 
                verdict={result.verdict} 
                confidence={result.confidence} 
                claim={result.claim} 
              />
              
              <MetricsBar metrics={result.metrics} />

              <SourceTable verificationResults={result.verification_results} />

              <div className="mt-12 w-full">
                <div className="mono text-[9px] uppercase tracking-[3px] text-[#666] mb-8">Moderator Analysis</div>
                <BotBubble agent="Moderator" color="var(--mod)">
                  {result.moderator_reasoning}
                </BotBubble>
              </div>

              <DebateLog 
                proArguments={result.pro_arguments} 
                conArguments={result.con_arguments} 
                proSources={result.pro_sources} 
                conSources={result.con_sources}
              />

              <FeedbackPanel claim={result.claim} verdict={result.verdict} />
              
              <footer className="mt-24 pt-8 border-t flex justify-between mono text-[9px] text-[#555] uppercase tracking-widest w-full">
                <span>InsightSwarm</span>
                <span>V1.0.0-React</span>
              </footer>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
