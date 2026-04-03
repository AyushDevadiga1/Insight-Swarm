/**
 * useSSE.js
 *
 * Manages the EventSource connection to /stream.
 *
 * KEY FIX: Changed `enabled` boolean trigger → `runId` UUID trigger.
 * The old pattern used requestAnimationFrame(() => setSseEnabled(false))
 * which IMMEDIATELY closed the connection before any events arrived.
 * Now the hook only reconnects when `runId` changes — i.e. when the user
 * clicks "Verify". Safe to re-render without retriggering the connection.
 *
 * Also fixed:
 * - Auto-reconnect prevention (onerror closes intentionally, no retry loop)
 * - Heartbeat listener keeps the backend "alive" indicator updated
 * - DebateArena now mounts when DECOMPOSING/SEARCHING stages arrive
 */

import { useEffect, useRef, useCallback } from 'react';
import { useDebateStore } from '../store/useDebateStore';

const FLUSH_INTERVAL_MS = 150;  // How often to flush buffered agent text to state

export function useSSE(claim, runId) {
  const esRef             = useRef(null);   // EventSource instance
  const flushTimerRef     = useRef(null);   // setInterval handle for text flush
  const bufferRef         = useRef({});     // { 'PRO_1': 'accumulated text' }
  const closedOnPurpose   = useRef(false);  // prevents auto-reconnect after intentional close
  const retryCount        = useRef(0);      // Current retry count
  const reconnectTimerRef = useRef(null);   // Timeout handle for scheduled reconnect

  const {
    startRun,
    setStreamConnected,
    pushStage,
    appendStreamChunk,
    pushSource,
    setResult,
    setError,
    setHeartbeat,
    setSubClaims,
    setPendingReview,
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
    // Final flush of any remaining buffered text
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
    if (!claim || !runId) return;

    // Close any previous connection cleanly
    if (esRef.current) {
      closedOnPurpose.current = true;
      esRef.current.close();
      esRef.current = null;
    }

    closedOnPurpose.current = false;
    bufferRef.current = {};

    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    const url = `/stream?claim=${encodeURIComponent(claim)}&thread_id=${encodeURIComponent(runId)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setStreamConnected(true);
      retryCount.current = 0; // Reset retries on successful connection
      startFlushTimer();
    };

    // ── heartbeat — backend is alive, update timestamp ────────────────────
    es.addEventListener('heartbeat', (e) => {
      try {
        setHeartbeat(Date.now());
      } catch (_) {}
    });

    // ── stage event ──────────────────────────────────────────────────────────
    es.addEventListener('stage', (e) => {
      try {
        pushStage(JSON.parse(e.data));
      } catch (_) {}
    });

    // ── sub_claims event — claim was decomposed ──────────────────────────────
    es.addEventListener('sub_claims', (e) => {
      try {
        const { claims } = JSON.parse(e.data);
        setSubClaims(claims);
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

    // ── source event ─────────────────────────────────────────────────────────
    es.addEventListener('source', (e) => {
      try {
        pushSource(JSON.parse(e.data));
      } catch (_) {}
    });

    // ── verdict event — final result ─────────────────────────────────────────
    es.addEventListener('verdict', (e) => {
      try {
        stopFlushTimer();
        setResult(JSON.parse(e.data));
        closedOnPurpose.current = true;
        es.close();
        esRef.current = null;
      } catch (_) {
        setError({ type: 'PARSE_ERROR', message: 'Could not parse final verdict.' });
      }
    });

    // ── human_review_required event — Wait for human intervention ────────────
    es.addEventListener('human_review_required', (e) => {
      try {
        stopFlushTimer();
        setPendingReview(JSON.parse(e.data));
        closedOnPurpose.current = true;
        es.close();
        esRef.current = null;
      } catch (_) {
        setError({ type: 'PARSE_ERROR', message: 'Could not parse human review request.' });
      }
    });

    // ── error event — backend-emitted structured error ───────────────────────
    es.addEventListener('error', (e) => {
      try {
        stopFlushTimer();
        setError(JSON.parse(e.data));
      } catch (_) {
        setError({ type: 'SYSTEM_ERROR', message: 'Unknown error from server.' });
      }
      closedOnPurpose.current = true;
      es.close();
      esRef.current = null;
    });

    // ── done event — stream closed cleanly ───────────────────────────────────
    es.addEventListener('done', () => {
      stopFlushTimer();
      closedOnPurpose.current = true;
      es.close();
      esRef.current = null;
    });

    // ── Network/connection error with exponential backoff ───────────────────────
    es.onerror = () => {
      if (closedOnPurpose.current) return;
      
      stopFlushTimer();
      es.close();
      esRef.current = null;
      
      if (retryCount.current < 5) {
        const delay = Math.min(2000 * Math.pow(2, retryCount.current), 30000);
        retryCount.current++;
        console.warn(`[SSE] Connection lost. Reconnecting in ${delay}ms (Attempt ${retryCount.current}/5)...`);
        
        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, delay);
      } else {
        closedOnPurpose.current = true;
        setError({
          type: 'NETWORK_ERROR',
          message: 'Lost connection to server. Connection retries exhausted. Please try again.',
        });
      }
    };
  }, [claim, runId, setStreamConnected, pushStage, pushSource, setResult, setError,
      setHeartbeat, setSubClaims, startFlushTimer, stopFlushTimer]);

  // ── Lifecycle — reconnects ONLY when runId changes (user clicks Verify) ────
  useEffect(() => {
    if (runId && claim) {
      startRun(runId);
      connect();
    }
    return () => {
      stopFlushTimer();
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (esRef.current) {
        closedOnPurpose.current = true;
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [runId]); // eslint-disable-line react-hooks/exhaustive-deps
  // Note: only runId in deps — this is intentional.
  // claim and connect are captured at trigger time; runId changing is the sole trigger.
}
