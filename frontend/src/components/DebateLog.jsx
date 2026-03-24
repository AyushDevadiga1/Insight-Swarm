import React, { useState } from 'react';
import BotBubble from './BotBubble';

const DebateLog = ({ proArguments, conArguments, proSources, conSources }) => {
  const [activeRound, setActiveRound] = useState(0);
  const proLen = proArguments ? proArguments.length : 0;
  const conLen = conArguments ? conArguments.length : 0;
  const rounds = Math.min(proLen, conLen);

  if (rounds === 0) return null;

  return (
    <div className="w-full max-w-4xl mt-10 animate-fade-in">
      <div className="flex items-center gap-2 border-b mb-8 overflow-x-auto pb-px">
        <span className="mono text-[9px] uppercase tracking-[3px] text-[#666] mr-4">Debate Log</span>
        {Array.from({ length: rounds }).map((_, i) => (
          <button
            key={i}
            onClick={() => setActiveRound(i)}
            className={`px-4 py-2 mono text-[10px] uppercase tracking-wider transition-all
              ${activeRound === i ? 'text-white border-b-2' : 'text-[#666] hover:text-[#999]'}
            `}
            style={activeRound === i ? { borderBottomColor: 'var(--accent)' } : {}}
          >
            Round {i + 1}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-2 w-full">
        <BotBubble 
          agent="ProAgent" 
          color="var(--pro)" 
          sources={proSources[activeRound] || []}
        >
          {proArguments[activeRound]}
        </BotBubble>
        
        <BotBubble 
          agent="ConAgent" 
          color="var(--con)" 
          sources={conSources[activeRound] || []}
        >
          {conArguments[activeRound]}
        </BotBubble>
      </div>
    </div>
  );
};

export default DebateLog;
