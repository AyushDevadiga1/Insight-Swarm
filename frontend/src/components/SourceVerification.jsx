import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function SourceVerification({ verificationResults = [] }) {
  const [expanded, setExpanded] = useState(false);

  if (!verificationResults || verificationResults.length === 0) return null;

  const TIER_LABEL = { 1: 'Tier 1 – Authoritative', 2: 'Tier 2 – Credible', 3: 'Tier 3 – Low Trust' };
  const TIER_COLOR = { 1: 'var(--pro)', 2: 'var(--fact)', 3: 'var(--orange)' };

  const verified   = verificationResults.filter(r => r.verified);
  const unverified = verificationResults.filter(r => !r.verified);

  return (
    <div className="glass" style={{ width: '100%', marginBottom: 24 }}>
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer"
        onClick={() => setExpanded(e => !e)}
        style={{ borderBottom: expanded ? '1px solid var(--border)' : 'none' }}
      >
        <div className="flex items-center gap-3">
          <span className="mono text-xs tracking-wider uppercase text-muted">🔍 Source Verification</span>
          <span style={{ background: 'rgba(34,211,165,0.12)', color: 'var(--pro)', padding: '1px 8px', borderRadius: 4, fontSize: 11, fontFamily: 'var(--mono)' }}>
            {verified.length}/{verificationResults.length} verified
          </span>
        </div>
        <span className={`chevron text-muted ${expanded ? 'open' : ''}`}>▼</span>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ padding: '12px 16px', maxHeight: 320, overflowY: 'auto' }}>
              {verificationResults.map((src, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  padding: '8px 0', borderBottom: '1px solid var(--border)',
                }}>
                  {/* Status icon */}
                  <span style={{ fontSize: 14, marginTop: 2, flexShrink: 0 }}>
                    {src.verified ? '✅' : '❌'}
                  </span>

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <a
                      href={src.url || src.source}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs truncate"
                      style={{ color: 'var(--fact)', display: 'block', maxWidth: '100%' }}
                    >
                      {(src.url || src.source || 'Unknown').replace(/^https?:\/\/(www\.)?/, '')}
                    </a>
                    <div className="flex items-center gap-2 mt-1">
                      {src.trust_tier && (
                        <span className="text-xs" style={{ color: TIER_COLOR[src.trust_tier] }}>
                          {TIER_LABEL[src.trust_tier] || src.trust_tier}
                        </span>
                      )}
                      {src.match_score != null && (
                        <span className="mono text-xs text-muted">
                          {Math.round(src.match_score * 100)}% match
                        </span>
                      )}
                    </div>
                    {src.error && (
                      <span className="text-xs" style={{ color: 'var(--red)', opacity: 0.8 }}>{src.error}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
