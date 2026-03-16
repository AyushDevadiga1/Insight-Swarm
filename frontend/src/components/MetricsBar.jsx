import React from 'react';

const MetricsBar = ({ metrics }) => {
  if (!metrics) return null;

  const m = [
    { label: 'Evidence Credibility', value: `${Math.round(metrics.credibility * 100)}%` },
    { label: 'Fallacy Count', value: metrics.fallacies || 0 },
    { label: 'Rebuttal Balance', value: parseFloat(metrics.balance || 0.5).toFixed(2) }
  ];

  return (
    <div className="w-full max-w-4xl mt-10 animate-fade-in">
      <div className="mono text-[9px] uppercase tracking-[3px] text-[#666] mb-4">Intelligence Metrics</div>
      <div className="grid grid-cols-3 gap-6">
        {m.map((item, i) => (
          <div key={i} className="bg-surface2 border p-6 flex flex-col gap-2">
            <span className="mono text-[9px] uppercase tracking-widest text-[#666]">{item.label}</span>
            <span className="mono text-3xl font-bold text-white leading-none">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default MetricsBar;
