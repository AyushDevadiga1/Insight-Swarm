import React from 'react';

const PipelineProgress = ({ active }) => {
  const stages = [
    { name: 'ProAgent', id: 1 },
    { name: 'ConAgent', id: 2 },
    { name: 'FactCheck', id: 3 },
    { name: 'Moderator', id: 4 }
  ];

  if (!active) return null;

  return (
    <div className="w-full max-w-4xl border flex mb-10 overflow-hidden animate-fade-in">
      {stages.map((stage) => {
        const isCurrent = active === stage.id;
        const isCompleted = active > stage.id;
        
        return (
          <div 
            key={stage.id} 
            className={`flex-1 flex flex-col items-center justify-center p-3 border-r last:border-r-0 transition-all
              ${isCurrent ? 'bg-amber/5 border-b-2' : ''}
              ${isCompleted ? 'bg-pro/5' : ''}
            `}
            style={isCurrent ? { borderBottomColor: 'var(--accent)' } : {}}
          >
            <span className={`mono text-lg leading-none mb-1
              ${isCurrent ? 'text-amber' : isCompleted ? 'text-pro' : 'text-[#444]'}
            `}>
              {isCompleted ? '✓' : stage.id}
            </span>
            <span className={`mono text-[9px] uppercase tracking-wider
              ${isCurrent ? 'text-amber' : isCompleted ? 'text-pro' : 'text-[#666]'}
            `}>
              {stage.name}
            </span>
          </div>
        );
      })}
    </div>
  );
};

export default PipelineProgress;
