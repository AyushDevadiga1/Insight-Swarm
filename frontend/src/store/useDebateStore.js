/**
 * useDebateStore.js
 * 
 * Central Zustand store for all debate state.
 * Replaces the chain of useState calls in App.jsx.
 * 
 * Key design decisions:
 * - agentMessages is a Map keyed by `${agent}_${round}` so updates
 *   are O(1) and don't cause other round/agent re-renders
 * - stages is an ordered array so LiveTimeline just maps over it
 * - throttledChunks: raw SSE text chunks are buffered here and
 *   flushed to agentMessages every 80ms via the useSSE hook
 */

import { create } from 'zustand';

// Stage definitions with display metadata
export const STAGES = {
  idle:           { label: 'Idle',             pct: 0,    icon: '◈' },
  consensus_check:{ label: 'Consensus Check',  pct: 0.05, icon: '🔬' },
  searching:      { label: 'Evidence Search',  pct: 0.10, icon: '🔍' },
  round_1_pro:    { label: 'ProAgent — Rd 1',  pct: 0.22, icon: '💬' },
  round_1_con:    { label: 'ConAgent — Rd 1',  pct: 0.35, icon: '🔴' },
  round_2_pro:    { label: 'ProAgent — Rd 2',  pct: 0.47, icon: '💬' },
  round_2_con:    { label: 'ConAgent — Rd 2',  pct: 0.58, icon: '🔴' },
  round_3_pro:    { label: 'ProAgent — Rd 3',  pct: 0.70, icon: '💬' },
  round_3_con:    { label: 'ConAgent — Rd 3',  pct: 0.80, icon: '🔴' },
  fact_checking:  { label: 'FactChecker',       pct: 0.88, icon: '✅' },
  moderating:     { label: 'Moderator',         pct: 0.95, icon: '⚖️' },
  complete:       { label: 'Complete',          pct: 1.00, icon: '🎉' },
  error:          { label: 'Error',             pct: 0,    icon: '❌' },
};

const initialState = {
  // Input
  claim: '',
  
  // Stream state
  isRunning: false,
  streamConnected: false,
  activeStage: 'idle',
  
  // Timeline — array of { stage, message, timestamp, elapsed }
  stageHistory: [],
  
  // Agent messages — keyed by `${agent}_${round}`, value is string
  // e.g. agentMessages['PRO_1'] = "Coffee contains antioxidants..."
  agentMessages: {},
  
  // Text being streamed right now (before flush to agentMessages)
  streamingAgent: null,   // 'PRO' | 'CON' | null
  streamingRound: null,   // 1 | 2 | 3 | null
  streamingBuffer: '',    // raw chars not yet flushed
  
  // Source verifications as they arrive
  sourceResults: [],
  
  // Final result (set on 'verdict' event)
  result: null,
  
  // Error info
  error: null,
  
  // Session history for sidebar
  history: [],
};

export const useDebateStore = create((set, get) => ({
  ...initialState,

  // ── Actions ──────────────────────────────────────────────────────────────

  setClaim: (claim) => set({ claim }),

  startRun: () => set({
    isRunning: true,
    streamConnected: false,
    activeStage: 'idle',
    stageHistory: [],
    agentMessages: {},
    streamingAgent: null,
    streamingRound: null,
    streamingBuffer: '',
    sourceResults: [],
    result: null,
    error: null,
  }),

  setStreamConnected: (connected) => set({ streamConnected: connected }),

  /** Called when a 'stage' SSE event arrives */
  pushStage: (stageData) => set((state) => ({
    activeStage: stageData.stage,
    stageHistory: [
      ...state.stageHistory,
      {
        stage: stageData.stage,
        message: stageData.message,
        progress: stageData.progress,
        elapsed: stageData.elapsed,
        timestamp: Date.now(),
      }
    ]
  })),

  /** Called when an 'agent_text' SSE chunk arrives — buffered, flushed by hook */
  appendStreamChunk: (agent, round, chunk) => set((state) => {
    const key = `${agent}_${round}`;
    return {
      streamingAgent: agent,
      streamingRound: round,
      agentMessages: {
        ...state.agentMessages,
        [key]: (state.agentMessages[key] || '') + chunk,
      }
    };
  }),

  /** Called when a 'source' SSE event arrives */
  pushSource: (sourceData) => set((state) => ({
    sourceResults: [...state.sourceResults, sourceData],
  })),

  /** Called when the 'verdict' SSE event arrives */
  setResult: (result) => set((state) => {
    const newEntry = { claim: result.claim, verdict: result.verdict, timestamp: Date.now() };
    return {
      isRunning: false,
      streamConnected: false,
      activeStage: 'complete',
      result,
      error: null,
      history: [newEntry, ...state.history].slice(0, 15),
    };
  }),

  /** Called on SSE 'error' event or network failure */
  setError: (error) => set({
    isRunning: false,
    streamConnected: false,
    activeStage: 'error',
    error,
    result: null,
  }),

  reset: () => set({
    ...initialState,
    history: get().history, // preserve session history on reset
  }),
}));
