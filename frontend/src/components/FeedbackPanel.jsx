import React, { useState } from 'react';
import { ThumbsUp, ThumbsDown, Check } from 'lucide-react';
import { submitFeedback } from '../api';

const FeedbackPanel = ({ claim, verdict }) => {
  const [submitted, setSubmitted] = useState(null);

  const handleFeedback = async (val) => {
    const ok = await submitFeedback(claim, verdict, val);
    if (ok) setSubmitted(val);
  };

  if (submitted) {
    return (
      <div className="w-full max-w-4xl mt-12 pt-8 border-t flex items-center gap-3 animate-fade-in">
        <div className="w-6 h-6 rounded-full bg-pro/20 text-pro flex items-center justify-center">
          <Check size={14} />
        </div>
        <p className="mono text-[10px] text-[#666] uppercase tracking-wider">
          {submitted === 'UP' ? 'Marked accurate — thank you.' : 'Flagged for human review.'}
        </p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mt-12 pt-8 border-t animate-fade-in">
      <div className="mono text-[9px] uppercase tracking-[3px] text-[#666] mb-6">Feedback Protocol</div>
      <div className="flex gap-4">
        <button 
          onClick={() => handleFeedback('UP')}
          className="flex items-center gap-2 px-6 py-3 border border-pro text-pro hover:bg-pro/5 mono text-[11px] uppercase tracking-widest transition-colors bg-transparent"
        >
          <ThumbsUp size={16} /> Accurate
        </button>
        <button 
          onClick={() => handleFeedback('DOWN')}
          className="flex items-center gap-2 px-6 py-3 border border-con text-con hover:bg-con/5 mono text-[11px] uppercase tracking-widest transition-colors bg-transparent"
        >
          <ThumbsDown size={16} /> Inaccurate
        </button>
      </div>
    </div>
  );
};

export default FeedbackPanel;
