import React, { useState, useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';

const ApiError = ({ error }) => {
  const [seconds, setSeconds] = useState(error.retry_after || 60);

  useEffect(() => {
    if (error.type !== 'RATE_LIMITED') return;
    
    const timer = setInterval(() => {
      setSeconds(prev => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    
    return () => clearInterval(timer);
  }, [error]);

  if (error.type === 'RATE_LIMITED') {
    return (
      <div className="w-full max-w-4xl p-6 border border-con bg-con/5 mt-8 animate-fade-in">
        <div className="flex items-center gap-3 text-con mb-3">
          <AlertTriangle size={20} />
          <h4 className="mono text-xs uppercase font-bold tracking-widest">API Resources Exhausted</h4>
        </div>
        <p className="text-sm text-[#999] leading-relaxed mb-4">
          All Groq and Gemini API keys are currently rate-limited. 
          The system automatically tried every available key and fallback provider.
          Please wait for the cooldown period before retrying.
        </p>
        <div className="mono text-4xl font-bold text-amber">
          {seconds}s
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl p-6 border border-con bg-con/5 mt-8 animate-fade-in text-con">
      <div className="flex items-center gap-3 mb-2">
        <AlertTriangle size={18} />
        <h4 className="mono text-xs uppercase font-bold tracking-widest">System Error</h4>
      </div>
      <p className="text-sm opacity-80">{error.message || 'An unexpected error occurred.'}</p>
    </div>
  );
};

export default ApiError;
