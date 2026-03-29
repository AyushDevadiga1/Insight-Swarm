/**
 * useApiStatusStore.js
 * 
 * Zustand store for LLM provider health status.
 * Polls /api/status every 30 seconds.
 * Exposed to sidebar ApiStatusPanel and to ErrorBanner
 * so errors show which provider failed and why.
 */

import { create } from 'zustand';

// Human-readable labels and colors for each status value
export const STATUS_META = {
  healthy:      { label: 'Healthy',       color: '#22c55e', dot: '●' },
  rate_limited: { label: 'Rate Limited',  color: '#f59e0b', dot: '●' },
  circuit_open: { label: 'Circuit Open',  color: '#f59e0b', dot: '◑' },
  no_key:       { label: 'Not Configured',color: '#444444', dot: '○' },
  no_credits:   { label: 'No Credits',    color: '#ef4444', dot: '✕' },
  invalid_key:  { label: 'Invalid Key',   color: '#ef4444', dot: '✕' },
  dns_error:    { label: 'DNS Failure',   color: '#ef4444', dot: '✕' },
  unknown:      { label: 'Unknown',       color: '#555555', dot: '?' },
};

// Provider display order and display names
export const PROVIDER_META = {
  groq:       { displayName: 'Groq',       subtitle: 'Llama 3.3 70B' },
  gemini:     { displayName: 'Gemini',     subtitle: 'Gemini 2.0 Flash' },
  cerebras:   { displayName: 'Cerebras',   subtitle: 'Llama 3.1 8B' },
  openrouter: { displayName: 'OpenRouter', subtitle: 'Multi-model' },
  tavily:     { displayName: 'Tavily',     subtitle: 'Web search' },
};

export const useApiStatusStore = create((set, get) => ({
  providers: {},       // { groq: { status, keys_available, ... }, ... }
  lastChecked: null,   // Date
  isLoading: false,
  error: null,
  _pollTimer: null,
  _consecutiveFailures: 0,   // backoff counter

  /** Fetch provider status from /api/status */
  fetchStatus: async () => {
    set({ isLoading: true });
    // AbortController for compatibility — AbortSignal.timeout() not in all browsers
    const controller = new AbortController();
    const timeoutId  = setTimeout(() => controller.abort(), 8000);
    try {
      const res = await fetch('/api/status', { signal: controller.signal });
      clearTimeout(timeoutId);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      set({ providers: data, lastChecked: new Date(), isLoading: false,
            error: null, _consecutiveFailures: 0 });
    } catch (err) {
      clearTimeout(timeoutId);
      const failures = get()._consecutiveFailures + 1;
      set({ isLoading: false, error: err.message, _consecutiveFailures: failures });
      // After 3 failures, slow down polling to 60s to reduce noise
      if (failures === 3) {
        const { _pollTimer } = get();
        if (_pollTimer) {
          clearInterval(_pollTimer);
          const timer = setInterval(() => get().fetchStatus(), 60_000);
          set({ _pollTimer: timer });
        }
      }
    }
  },

  /** Start polling every 30 seconds. Call once from App on mount. */
  startPolling: () => {
    const { fetchStatus, _pollTimer } = get();
    if (_pollTimer) return; // already polling

    fetchStatus(); // immediate first fetch

    const timer = setInterval(() => {
      fetchStatus();
    }, 30_000);

    set({ _pollTimer: timer });
  },

  /** Stop polling (call on unmount) */
  stopPolling: () => {
    const { _pollTimer } = get();
    if (_pollTimer) {
      clearInterval(_pollTimer);
      set({ _pollTimer: null });
    }
  },

  /**
   * Returns a human-readable summary of what's broken.
   * Used by ErrorBanner to give the user context.
   */
  getErrorContext: () => {
    const { providers } = get();
    const broken = Object.entries(providers)
      .filter(([, info]) => !['healthy', 'no_key'].includes(info.status))
      .map(([name, info]) => {
        const meta = STATUS_META[info.status] || STATUS_META.unknown;
        const display = PROVIDER_META[name]?.displayName || name;
        return `${display}: ${meta.label}`;
      });
    return broken.length > 0 ? broken.join(' · ') : null;
  },

  /** Returns true if at least one primary provider (groq or gemini) is healthy */
  hasPrimaryProvider: () => {
    const { providers } = get();
    return (
      providers.groq?.status === 'healthy' ||
      providers.gemini?.status === 'healthy'
    );
  },
}));
