import React from 'react';

const SourceTable = ({ verificationResults }) => {
  if (!verificationResults || verificationResults.length === 0) return null;

  return (
    <div className="w-full max-w-4xl mt-10 animate-fade-in">
      <div className="flex items-center gap-4 border-b pb-2 mb-4">
        <span className="mono text-[9px] uppercase tracking-[3px] text-[#666]">Source Verification</span>
      </div>
      
      <div className="flex flex-col border">
        {verificationResults.map((res, i) => {
          const isVerified = res.status === "VERIFIED";
          return (
            <div key={i} className="flex items-center gap-4 p-3 border-b last:border-0 hover:bg-surface2 transition-colors">
              <span className="mono text-[9px] text-[#444] w-6 shrink-0">{(i + 1).toString().padStart(2, '0')}</span>
              <div className="flex-1 min-w-0">
                <a 
                  href={res.url} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className={`text-[12px] truncate block ${isVerified ? 'text-[#ccc]' : 'text-con hover:underline'}`}
                >
                  {res.url}
                </a>
                {!isVerified && res.error && (
                  <span className="text-[10px] text-[#666] block truncate">{res.error}</span>
                )}
              </div>
              <div className={`px-2 py-0.5 mono text-[9px] border rounded shrink-0
                ${isVerified ? 'border-pro text-pro' : 'border-con text-con'}
              `} style={{ borderColor: isVerified ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)' }}>
                {isVerified ? 'VERIFIED' : 'FAILED'}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SourceTable;
