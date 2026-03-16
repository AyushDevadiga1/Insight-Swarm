import React from 'react';

const VerdictCard = ({ verdict, confidence, claim }) => {
  const getVerdictClass = (v) => {
    const verdictStr = (v || "").toUpperCase();
    if (["TRUE", "CORRECT", "ACCURATE", "SUPPORTED", "VERIFIED"].some(k => verdictStr.includes(k))) return 'vt';
    if (["FALSE", "INCORRECT", "INACCURATE", "UNSUPPORTED", "DEBUNKED"].some(k => verdictStr.includes(k))) return 'vf';
    if (["UNCERTAIN", "MIXED", "PARTIAL", "INSUFFICIENT", "UNVERIFIED", "EVIDENCE", "RATE_LIMITED", "UNKNOWN"].some(k => verdictStr.includes(k))) return 'vu';
    return 'vx';
  };

  const vClass = getVerdictClass(verdict);
  const colorMap = {
    vt: 'var(--pro)',
    vf: 'var(--con)',
    vu: 'var(--accent)',
    vx: 'var(--text-secondary)'
  };
  const color = colorMap[vClass];
  const pct = Math.round(confidence * 100);

  return (
    <div 
      className="w-full p-6 border-l-4 border-t border-r border-b bg-surface transition-all animate-fade-in mb-8"
      style={{ borderLeftColor: color }}
    >
      <div className="mono text-[9px] uppercase tracking-[4px] text-[#999] mb-2">Verdict</div>
      <div className="text-4xl font-bold mono uppercase leading-none mb-2" style={{ color }}>
        {verdict || 'UNKNOWN'}
      </div>
      {claim && (
        <div className="text-[13px] text-[#777] italic mb-6 leading-relaxed">
          "{claim}"
        </div>
      )}
      <div className="flex flex-col gap-1.5 mt-4">
        <div className="w-full h-0.5 bg-[#222] relative overflow-hidden">
          <div 
            className="h-full absolute left-0 top-0 transition-all"
            style={{ width: `${pct}%`, backgroundColor: color, transitionDuration: '1000ms' }}
          />
        </div>
        <div className="flex justify-between mono text-[10px] text-[#666]">
          <span>Confidence</span>
          <span>{pct}%</span>
        </div>
      </div>
    </div>
  );
};

export default VerdictCard;
