/**
 * VerdictCard.jsx — v3
 * Large verdict, animated confidence bar, model chips
 */

import React, { useState, useEffect } from 'react';

function verdictMeta(verdict) {
  const v = (verdict || '').toUpperCase();
  if (['TRUE', 'CORRECT', 'ACCURATE', 'SUPPORTED', 'MOSTLY TRUE'].some(k => v.includes(k)))
    return { cls: 'true',      icon: '✅', valueCls: '',                    iconCls: '',                    fillCls: '' };
  if (['FALSE', 'INCORRECT', 'INACCURATE', 'DEBUNKED', 'MOSTLY FALSE'].some(k => v.includes(k)))
    return { cls: 'false',     icon: '❌', valueCls: 'verdict-value-false', iconCls: 'verdict-icon-false',   fillCls: 'verdict-conf-fill-false' };
  if (['PARTIAL', 'INSUFFICIENT', 'UNKNOWN', 'UNCERTAIN', 'MIXED'].some(k => v.includes(k)))
    return { cls: 'uncertain', icon: '⚠️', valueCls: 'verdict-value-uncertain', iconCls: 'verdict-icon-uncertain', fillCls: 'verdict-conf-fill-uncertain' };
  return { cls: 'uncertain', icon: '🔍', valueCls: 'verdict-value-uncertain', iconCls: 'verdict-icon-uncertain', fillCls: 'verdict-conf-fill-uncertain' };
}

export default function VerdictCard({ result }) {
  const { verdict, confidence, claim, is_cached } = result;
  const meta  = verdictMeta(verdict);
  const pct   = Math.round((confidence || 0) * 100);

  const [displayPct, setDisplayPct] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setDisplayPct(pct), 100);
    return () => clearTimeout(t);
  }, [pct]);

  return (
    <div className="verdict-card">
      <div className="verdict-card-top">
        <div className={`verdict-icon ${meta.iconCls}`}>
          {meta.icon}
        </div>
        <div className="verdict-text-block" style={{ flex: 1 }}>
          <div className="verdict-label-sm">Verdict</div>
          <div className={`verdict-value ${meta.valueCls}`}>
            {verdict || 'Unknown'}
          </div>
          {claim && (
            <div className="verdict-claim-text">"{claim}"</div>
          )}
        </div>
        {is_cached && (
          <div className="verdict-cached-badge">💾 cached</div>
        )}
      </div>

      <div className="verdict-card-bottom">
        <div className="verdict-conf-row">
          <span className="verdict-conf-label">Confidence</span>
          <span className={`verdict-conf-pct ${meta.cls === 'false' ? 'verdict-conf-pct-false' : ''}`}>
            {pct}%
          </span>
        </div>
        <div className="verdict-conf-track">
          <div
            className={`verdict-conf-fill ${meta.fillCls}`}
            style={{ width: `${displayPct}%` }}
          />
        </div>

        {(result.pro_model_used || result.con_model_used || result.moderator_model_used) && (
          <div className="verdict-model-chips">
            {result.pro_model_used       && <span className="model-chip">🛡️ {result.pro_model_used}</span>}
            {result.con_model_used       && <span className="model-chip">⚔️ {result.con_model_used}</span>}
            {result.moderator_model_used && <span className="model-chip">⚖️ {result.moderator_model_used}</span>}
          </div>
        )}
      </div>
    </div>
  );
}
