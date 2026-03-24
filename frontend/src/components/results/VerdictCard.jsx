/**
 * VerdictCard.jsx
 * 
 * Displays the final verdict with animated confidence bar.
 * Uses framer-motion for the entrance animation only —
 * the confidence bar fill uses a CSS transition.
 */

import React, { useState, useEffect } from 'react';

function verdictClass(verdict) {
  const v = (verdict || '').toUpperCase();
  if (['TRUE', 'CORRECT', 'ACCURATE', 'SUPPORTED'].some(k => v.includes(k))) return 'vt';
  if (['FALSE', 'INCORRECT', 'INACCURATE', 'DEBUNKED'].some(k => v.includes(k))) return 'vf';
  if (['PARTIAL', 'INSUFFICIENT', 'UNKNOWN', 'RATE_LIMITED'].some(k => v.includes(k))) return 'vu';
  return 'vx';
}

const CLASS_COLOR = {
  vt: 'var(--pro)',
  vf: 'var(--con)',
  vu: 'var(--amber)',
  vx: 'var(--text-secondary)',
};

const VERDICT_EMOJI = {
  TRUE: '✅',
  FALSE: '❌',
  'PARTIALLY TRUE': '⚠️',
  'INSUFFICIENT EVIDENCE': '🔍',
  RATE_LIMITED: '⏱',
  SYSTEM_ERROR: '⚙️',
};

export default function VerdictCard({ result }) {
  const { verdict, confidence, claim, is_cached } = result;
  const vc = verdictClass(verdict);
  const color = CLASS_COLOR[vc];
  const pct = Math.round((confidence || 0) * 100);
  const emoji = VERDICT_EMOJI[verdict] || '⚖️';

  // Animate bar from 0 after mount
  const [displayPct, setDisplayPct] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setDisplayPct(pct), 80);
    return () => clearTimeout(t);
  }, [pct]);

  return (
    <div className="verdict-card" style={{ '--verdict-color': color }}>
      {is_cached && (
        <div className="verdict-cache-badge">💾 Cached result</div>
      )}

      <div className="verdict-label">Verdict</div>

      <div className="verdict-emoji">{emoji}</div>

      <div className="verdict-value">{verdict || 'UNKNOWN'}</div>

      {claim && (
        <blockquote className="verdict-claim">"{claim}"</blockquote>
      )}

      {/* Confidence bar */}
      <div className="verdict-conf-wrap">
        <div className="verdict-conf-track">
          <div
            className="verdict-conf-fill"
            style={{ width: `${displayPct}%` }}
          />
        </div>
        <div className="verdict-conf-labels">
          <span>Confidence</span>
          <span className="verdict-conf-pct">{pct}%</span>
        </div>
      </div>
    </div>
  );
}
