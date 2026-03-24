import React from 'react';
import { Shield, Zap, Search, Scale } from 'lucide-react';

const Sidebar = ({ onExampleClick, history = [] }) => {
  const agents = [
    { name: 'ProAgent', num: '01', desc: 'Validates claim assumptions', color: 'var(--pro)', icon: Shield },
    { name: 'ConAgent', num: '02', desc: 'Adversarial rebuttal', color: 'var(--con)', icon: Zap },
    { name: 'FactChecker', num: '03', desc: 'Source verification', color: 'var(--fact)', icon: Search },
    { name: 'Moderator', num: '04', desc: 'Consensus & fallacy detection', color: 'var(--mod)', icon: Scale },
  ];

  const examples = [
    "Coffee prevents cancer",
    "Exercise improves mental health",
    "The Earth is flat",
    "Vaccines cause autism",
    "AI will replace all jobs by 2030",
  ];

  return (
    <aside className="w-80 h-full border-r bg-surface p-6 flex flex-col gap-8 overflow-y-auto shrink-0">
      <div>
        <h2 className="mono text-[9px] text-[#666] tracking-[4px] uppercase mb-4">Agent Architecture</h2>
        <div className="flex flex-col gap-4">
          {agents.map((agent) => (
            <div key={agent.name} className="py-2 border-b">
              <div className="flex items-center gap-3 mb-1">
                <span className="mono text-[9px] text-[#444]">{agent.num}</span>
                <span className="font-medium text-[13px]" style={{ color: agent.color }}>{agent.name}</span>
              </div>
              <p className="text-[11px] text-[#777] leading-relaxed">{agent.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="mono text-[9px] text-[#666] tracking-[4px] uppercase mb-4">Example Claims</h2>
        <div className="flex flex-col gap-2">
          {examples.map((ex) => (
            <button
              key={ex}
              onClick={() => onExampleClick(ex)}
              className="text-left py-2 px-3 border text-[12px] text-[#888] hover:text-white hover:border-[#444] transition-all bg-transparent"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {history.length > 0 && (
        <div className="mt-auto pt-8">
          <h2 className="mono text-[9px] text-[#666] tracking-[4px] uppercase mb-4">Session History</h2>
          <div className="flex flex-col gap-2">
            {history.map((item, i) => (
              <div key={i} className="text-[11px] p-2 border bg-surface2">
                <p className="text-[#ccc] truncate mb-1">{item.claim}</p>
                <span className="mono text-[9px] px-1.5 py-0.5 rounded border border-[#333]" style={{ 
                  color: item.verdict.includes('TRUE') ? 'var(--pro)' : item.verdict.includes('FALSE') ? 'var(--con)' : 'var(--mod)'
                }}>
                  {item.verdict}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-8 p-3 border mono text-[9px] text-[#666] leading-loose">
        POWERED BY<br />
        <span className="text-white">GROQ + GEMINI</span>
      </div>
    </aside>
  );
};

export default Sidebar;
