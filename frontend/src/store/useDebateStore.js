/**
 * useDebateStore.js
 *
 * Central Zustand store for all debate state.
 *
 * Changes in this revision:
 * - Added DECOMPOSING and SUMMARIZING to STAGES map
 * - pushStage now deduplicates consecutive identical stages (prevents SSE
 *   reconnect doubling)
 * - Added lastHeartbeat timestamp and setHeartbeat action
 * - Added subClaims array for claim decomposition display
 * - appendStreamChunk skips empty chunks (prevents 80ms flush noise)
 */

import { create } from 'zustand';

// Stage definitions with display metadata
// Maps backend stage strings → UI label + progress %
export const STAGES = {
  idle:             { label: 'Idle',              pct: 0,    icon: '◈' },
  decomposing:      { label: 'Decomposing Claim', pct: 0.04, icon: '🔀' },
  searching:        { label: 'Evidence Search',   pct: 0.10, icon: '🔍' },
  consensus_check:  { label: 'Consensus Check',   pct: 0.15, icon: '🔬' },
  round_1_pro:      { label: 'ProAgent — Rd 1',   pct: 0.24, icon: '💬' },
  round_1_con:      { label: 'ConAgent — Rd 1',   pct: 0.36, icon: '🔴' },
  summarizing:      { label: 'Summarizing',        pct: 0.44, icon: '📝' },
  round_2_pro:      { label: 'ProAgent — Rd 2',   pct: 0.50, icon: '💬' },
  round_2_con:      { label: 'ConAgent — Rd 2',   pct: 0.60, icon: '🔴' },
  round_3_pro:      { label: 'ProAgent — Rd 3',   pct: 0.70, icon: '💬' },
  round_3_con:      { label: 'ConAgent — Rd 3',   pct: 0.80, icon: '🔴' },
  fact_checking:    { label: 'FactChecker',        pct: 0.88, icon: '✅' },
  moderating:       { label: 'Moderator',          pct: 0.95, icon: '⚖️' },
  complete:         { label: 'Complete',           pct: 1.00, icon: '🎉' },
  error:            { label: 'Error',              pct: 0,    icon: '❌' },
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

  // Source verifications as they arrive
  sourceResults: [],

  // Sub-claims from claim decomposition
  subClaims: [],

  // Heartbeat timestamp — updated every 3s by backend heartbeat events
  lastHeartbeat: null,

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
    sourceResults: [],
    subClaims: [],
    lastHeartbeat: null,
    result: null,
    error: null,
  }),

  setStreamConnected: (connected) => set({ streamConnected: connected }),

  /** Called when a 'stage' SSE event arrives.
   *  Deduplicates consecutive identical stages to prevent SSE-reconnect doubling. */
  pushStage: (stageData) => set((state) => {
    const last = state.stageHistory[state.stageHistory.length - 1];
    if (last && last.stage === stageData.stage) {
      // Identical stage — skip to prevent doubled entries on reconnect
      return { activeStage: stageData.stage };
    }
    return {
      activeStage: stageData.stage,
      stageHistory: [
        ...state.stageHistory,
        {
          stage:     stageData.stage,
          message:   stageData.message,
          progress:  stageData.progress,
          elapsed:   stageData.elapsed,
          timestamp: Date.now(),
        }
      ]
    };
  }),

  /** Called on heartbeat SSE events — keeps the "backend is alive" indicator fresh */
  setHeartbeat: (ts) => set({ lastHeartbeat: ts }),

  /** Called when sub_claims SSE event arrives */
  setSubClaims: (claims) => set({ subClaims: claims }),

  /** Called when an 'agent_text' SSE chunk arrives — buffered, flushed by useSSE hook */
  appendStreamChunk: (agent, round, chunk) => {
    if (!chunk) return; // skip empty flushes
    set((state) => {
      const key = `${agent}_${round}`;
      return {
        streamingAgent: agent,
        streamingRound: round,
        agentMessages: {
          ...state.agentMessages,
          [key]: (state.agentMessages[key] || '') + chunk,
        }
      };
    });
  },

  /** Called when a 'source' SSE event arrives */
  pushSource: (sourceData) => set((state) => ({
    sourceResults: [...state.sourceResults, sourceData],
  })),

  /** Called when the 'verdict' SSE event arrives */
  setResult: (result) => set((state) => {
    const newEntry = {
      claim:     result.claim,
      verdict:   result.verdict,
      timestamp: Date.now(),
    };
    return {
      isRunning:       false,
      streamConnected: false,
      activeStage:     'complete',
      result,
      error:           null,
      history:         [newEntry, ...state.history].slice(0, 15),
    };
  }),

  /** Called on SSE 'error' event or network failure */
  setError: (error) => set({
    isRunning:       false,
    streamConnected: false,
    activeStage:     'error',
    error,
    result:          null,
  }),

  reset: () => set({
    ...initialState,
    history: get().history, // preserve session history across resets
  }),
}));
