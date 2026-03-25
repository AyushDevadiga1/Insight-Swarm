/**
 * useSSE.js
 * 
 * React hook that manages a Server-Sent Events connection to /stream.
 * 
 * Responsibilities:
 * - Opens EventSource to /stream?claim={claim}
 * - Routes each event type to the appropriate Zustand store action
 * - Throttles 'agent_text' chunks: buffers for 80ms before flushing
 *   to prevent re-rendering the entire debate on every character
 * - Handles reconnection on transient network errors (max 3 retries)
 * - Cleans up EventSource on unmount or when claim changes
 */

import { useEffect, useRef, useCallback } from 'react';
import { useDebateStore } from '../store/useDebateStore';

const FLUSH_INTERVAL_MS = 80;   // How often to flush streamed agent text to state
const MAX_RETRIES = 3;

export function useSSE(claim, enabled) {
  const esRef = useRef(null);          // EventSource instance
  const flushTimerRef = useRef(null);  // setInterval handle for text flush
  const retryCountRef = useRef(0);
  const bufferRef = useRef({});        // { 'PRO_1': 'chunk text so far...' }

  const {
    startRun,
    setStreamConnected,
    pushStage,
    appendStreamChunk,
    pushSource,
    setResult,
    setError,
  } = useDebateStore.getState();

  // ── Flush buffered text chunks to Zustand every 80ms ───────────────────────
  const startFlushTimer = useCallback(() => {
    if (flushTimerRef.current) return;
    flushTimerRef.current = setInterval(() => {
      const buf = bufferRef.current;
      const keys = Object.keys(buf);
      if (keys.length === 0) return;
      keys.forEach(key => {
        if (buf[key]) {
          const [agent, round] = key.split('_');
          appendStreamChunk(agent, parseInt(round, 10), buf[key]);
          buf[key] = '';
        }
      });
    }, FLUSH_INTERVAL_MS);
  }, [appendStreamChunk]);

  const stopFlushTimer = useCallback(() => {
    if (flushTimerRef.current) {
      clearInterval(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    // Final flush of any remaining buffer
    const buf = bufferRef.current;
    Object.keys(buf).forEach(key => {
      if (buf[key]) {
        const [agent, round] = key.split('_');
        appendStreamChunk(agent, parseInt(round, 10), buf[key]);
        buf[key] = '';
      }
    });
    bufferRef.current = {};
  }, [appendStreamChunk]);

  // ── Open SSE connection ─────────────────────────────────────────────────────
  const connect = useCallback(() => {
    if (!claim || !enabled) return;

    // Close previous connection if any
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    const url = `/stream?claim=${encodeURIComponent(claim)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      retryCountRef.current = 0;
      setStreamConnected(true);
      startFlushTimer();
    };

    // ── stage event ──────────────────────────────────────────────────────────
    es.addEventListener('stage', (e) => {
      try {
        pushStage(JSON.parse(e.data));
      } catch (_) {}
    });

    // ── agent_text event — buffer, don't flush immediately ──────────────────
    es.addEventListener('agent_text', (e) => {
      try {
        const { agent, round, chunk } = JSON.parse(e.data);
        const key = `${agent}_${round}`;
        bufferRef.current[key] = (bufferRef.current[key] || '') + chunk;
      } catch (_) {}
    });

    // ── source event ────────────────────────────────────────────────────────
    es.addEventListener('source', (e) => {
      try {
        pushSource(JSON.parse(e.data));
      } catch (_) {}
    });

    // ── log event (informational backend messages) ─────────────────────────
    es.addEventListener('log', (e) => {
      // Silently consumed — could be shown in a debug panel
    });

    // ── verdict event — final result ────────────────────────────────────────
    es.addEventListener('verdict', (e) => {
      try {
        stopFlushTimer();
        setResult(JSON.parse(e.data));
        es.close();
        esRef.current = null;
      } catch (err) {
        setError({ type: 'PARSE_ERROR', message: 'Could not parse final verdict' });
      }
    });

    // ── error event — backend-emitted error ─────────────────────────────────
    es.addEventListener('error', (e) => {
      try {
        stopFlushTimer();
        setError(JSON.parse(e.data));
        es.close();
        esRef.current = null;
      } catch (_) {
        setError({ type: 'SYSTEM_ERROR', message: 'Unknown error from server' });
      }
    });

    // ── done event — stream completed ────────────────────────────────────────
    es.addEventListener('done', () => {
      stopFlushTimer();
      es.close();
      esRef.current = null;
    });

    // ── Network/connection error ─────────────────────────────────────────────
    es.onerror = (err) => {
      // EventSource auto-retries on transient failures.
      // We only give up after MAX_RETRIES consecutive errors.
      retryCountRef.current += 1;
      if (retryCountRef.current >= MAX_RETRIES) {
        stopFlushTimer();
        setError({
          type: 'NETWORK_ERROR',
          message: 'Lost connection to server. Please try again.',
        });
        es.close();
        esRef.current = null;
      }
    };
  }, [claim, enabled, setStreamConnected, pushStage, pushSource, setResult, setError, startFlushTimer, stopFlushTimer]);

  // ── Lifecycle ───────────────────────────────────────────────────────────────
  useEffect(() => {
    if (enabled && claim) {
      startRun();
      connect();
    }
    return () => {
      stopFlushTimer();
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [enabled, claim]); // eslint-disable-line react-hooks/exhaustive-deps
  
  // Note: connect/startRun/stopFlushTimer intentionally omitted from deps
  // to avoid reconnecting on every render. The enabled+claim combo is the trigger.
}
