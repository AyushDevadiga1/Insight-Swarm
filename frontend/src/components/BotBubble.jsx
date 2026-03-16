import React from 'react';

const BotBubble = ({ agent, color, children, sources = [] }) => {
  const initials = agent === 'FactChecker' ? 'FC' : agent[0];
  
  return (
    <div className="flex gap-4 mb-6 animate-fade-in">
      <div 
        className="w-10 h-10 rounded-full flex items-center justify-center shrink-0 border"
        style={{ borderColor: color, color: color, boxShadow: `0 0 10px ${color}33` }}
      >
        <span className="font-bold text-xs mono">{initials}</span>
      </div>
      <div className="flex flex-col gap-2 w-full">
        <div className="flex items-center gap-2">
          <span className="mono text-[10px] uppercase tracking-wider" style={{ color }}>{agent}</span>
        </div>
        <div className="bg-surface2 border p-4 rounded-r-xl rounded-bl-sm text-sm leading-relaxed text-[#ccc]">
          {children}
          
          {sources.length > 0 && (
            <div className="mt-4 pt-3 border-t">
              <span className="mono text-[9px] uppercase tracking-widest text-[#666] block mb-2">Sources Cited:</span>
              <div className="flex flex-col gap-1">
                {sources.map((url, i) => (
                  <a 
                    key={i} 
                    href={url} 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="text-[11px] text-[#3b82f6] hover:underline truncate"
                  >
                    {url}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BotBubble;
