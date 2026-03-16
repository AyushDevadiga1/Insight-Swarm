import React from 'react';

const EmptyState = () => {
  return (
    <div className="w-full max-w-4xl border border-dashed p-24 flex flex-col items-center justify-center text-center mt-10">
      <div className="text-7xl mono text-white opacity-5 mb-8 tracking-widest leading-none">◈</div>
      <h3 className="mono text-[11px] uppercase tracking-[0.4em] text-[#999] mb-4">Ready to Verify</h3>
      <p className="text-[13px] text-[#666] max-w-sm leading-relaxed">
        Type a claim and press <strong className="text-white">Verify Claim</strong>.<br />
        Four AI agents debate, fact-check, and deliver a verdict.
      </p>
    </div>
  );
};

export default EmptyState;
