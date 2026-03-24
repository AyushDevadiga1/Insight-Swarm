import React from 'react';
import { RefreshCw } from 'lucide-react';

const ClaimInput = ({ value, onChange, onVerify, onReset, disabled, loading }) => {
  const charCount = (value || "").trim().length;
  const isReady = charCount >= 10;

  return (
    <div className="w-full max-w-4xl flex flex-col gap-4 mb-8 text-white">
      <div className="flex flex-col gap-2">
        <label className="mono text-[9px] uppercase tracking-[0.3em] text-[#999]">Subject Claim</label>
        <div className="relative">
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Enter a natural-language claim to verify…"
            className="w-full h-24 p-4 text-[15px] resize-none border focus:border-amber transition-all"
            disabled={loading}
          />
          <div className="absolute mono text-[10px] text-[#666]" style={{ bottom: '12px', right: '12px' }}>
            {charCount} / 10 chars min
          </div>
        </div>
      </div>

      <div className="flex gap-4">
        <button
          onClick={onVerify}
          disabled={!isReady || loading || disabled}
          className={`flex-1 py-4 mono text-[11px] font-bold uppercase tracking-[0.2em] transition-all
            ${isReady && !loading ? 'bg-amber text-black' : 'bg-surface border text-[#444] cursor-not-allowed'}
          `}
        >
          {loading ? 'Verifying...' : 'Verify Claim'}
        </button>
        <button
          onClick={onReset}
          className="px-6 border text-[#999] hover:text-white hover:border-[#555] flex items-center justify-center transition-all"
        >
          <RefreshCw size={18} />
        </button>
      </div>
    </div>
  );
};

export default ClaimInput;
