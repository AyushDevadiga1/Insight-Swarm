/**
 * FallacyPanel.jsx — v3
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

export default function FallacyPanel({ result }) {
  const [expanded, setExpanded] = useState(false);

  const proFallacies = result?.metrics?.pro_fallacies || [];
  const conFallacies = result?.metrics?.con_fallacies || [];
  const total = proFallacies.length + conFallacies.length;

  if (total === 0) return null;

  return (
    <div className="fallacy-panel-wrap">
      <button className="fallacy-toggle" onClick={() => setExpanded(v => !v)}>
        <span className="section-label" style={{ margin: 0 }}>
          Logical fallacies detected ({total})
        </span>
        {expanded ? <ChevronUp size={14} color="var(--text-3)" /> : <ChevronDown size={14} color="var(--text-3)" />}
      </button>

      {expanded && (
        <div className="fallacy-columns">
          {proFallacies.length > 0 && (
            <div>
              <div className="fallacy-column-title" style={{ color: 'var(--pro)' }}>🛡️ ProAgent</div>
              <ul className="fallacy-items">
                {proFallacies.map((f, i) => (
                  <li key={i} className="fallacy-item" style={{ borderLeftColor: 'var(--pro-border)' }}>{f}</li>
                ))}
              </ul>
            </div>
          )}
          {conFallacies.length > 0 && (
            <div>
              <div className="fallacy-column-title" style={{ color: 'var(--con)' }}>⚔️ ConAgent</div>
              <ul className="fallacy-items">
                {conFallacies.map((f, i) => (
                  <li key={i} className="fallacy-item" style={{ borderLeftColor: 'var(--con-border)' }}>{f}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
