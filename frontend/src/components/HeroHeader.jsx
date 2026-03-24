import React from 'react';

const HeroHeader = () => {
  return (
    <div className="pt-10 pb-6 border-b-2 inline-block mb-10" style={{ borderBottomColor: 'white' }}>
      <h1 className="text-7xl font-bold mono uppercase leading-none tracking-wider">
        InsightSwarm
      </h1>
      <p className="mono text-[10px] text-[#999] tracking-[0.4em] uppercase mt-4">
        Multi-Agent Truth Verification Protocol
      </p>
    </div>
  );
};

export default HeroHeader;
