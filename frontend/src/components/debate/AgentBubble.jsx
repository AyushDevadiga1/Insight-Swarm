/**
 * AgentBubble.jsx
 * 
 * A single agent message bubble. Renders text that may still be streaming.
 * 
 * The parent (DebateArena) passes `text` which is the current value from
 * useDebateStore.agentMessages[`${agent}_${round}`]. As SSE chunks arrive
 * and the store updates at 80ms intervals, only this component re-renders
 * (not the whole app) because it reads a derived slice of state.
 * 
 * The typing cursor (|) is a CSS animation — no JS interval needed.
 */

import React from 'react';
import { useDebateStore } from '../../store/useDebateStore';

function getDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } 
  catch { return url; }
}

const AGENT_META = {
  PRO: {
    label: 'ProAgent',
    color: 'var(--pro)',
    avatar: 'P',
    side: 'left',
  },
  CON: {
    label: 'ConAgent',
    color: 'var(--con)',
    avatar: 'C',
    side: 'right',
  },
  MODERATOR: {
    label: 'Moderator',
    color: 'var(--mod)',
    avatar: 'M',
    side: 'center',
  },
};

export default function AgentBubble({ agent, round, text, isStreaming, sources = [] }) {
  const meta = AGENT_META[agent] || { label: agent, color: '#888', avatar: '?', side: 'left' };
  const isEmpty = !text;

  const sourceResults = useDebateStore(state => state.sourceResults || []);
  
  const enrichedSources = sources.map(url => {
    const verifiedData = sourceResults.find(r => r.url === url);
    return {
      url,
      domain: getDomain(url),
      status: verifiedData?.status || 'PENDING',
      trustScore: verifiedData?.trust_score ?? null,
      trustTier: verifiedData?.trust_tier || 'UNKNOWN',
      preview: verifiedData?.content_preview || null,
      error: verifiedData?.error || null
    };
  });

  return (
    <div className={`agent-bubble agent-bubble--${meta.side}`}>
      {/* Avatar */}
      <div className="agent-avatar" style={{ borderColor: meta.color, color: meta.color }}>
        {meta.avatar}
      </div>

      <div className="agent-bubble-body">
        {/* Header */}
        <div className="agent-bubble-header">
          <span className="agent-bubble-name" style={{ color: meta.color }}>
            {meta.label}
          </span>
          {round && (
            <span className="agent-bubble-round">Round {round}</span>
          )}
          {isStreaming && (
            <span className="agent-streaming-badge">● live</span>
          )}
        </div>

        {/* Content */}
        <div className={`agent-bubble-text ${isStreaming ? 'agent-bubble-text--streaming' : ''}`}>
          {isEmpty && isStreaming ? (
            <span className="agent-thinking">
              <span className="thinking-dot" />
              <span className="thinking-dot" />
              <span className="thinking-dot" />
            </span>
          ) : (
            <>
              {text}
              {isStreaming && <span className="typing-cursor" />}
            </>
          )}
        </div>

        {/* Sources cited — Claude-style hover cards */}
        {enrichedSources.length > 0 && !isStreaming && (
          <div className="agent-sources-chips-container">
            <div className="agent-sources-label">Sources:</div>
            <div className="agent-sources-chips">
              {enrichedSources.map((src, i) => (
                <div key={i} className="source-chip-wrapper">
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`source-chip status-${src.status.toLowerCase()}`}
                  >
                    [{i + 1}] {src.domain}
                  </a>
                  <div className="source-hover-card">
                    <div className="source-hc-header">
                      <span className={`source-hc-status badge-${src.status.toLowerCase()}`}>
                        {src.status.replace(/_/g, ' ')}
                      </span>
                      <span className="source-hc-domain">{src.domain}</span>
                    </div>
                    {src.error ? (
                      <div className="source-hc-error">{src.error}</div>
                    ) : src.preview ? (
                      <div className="source-hc-preview">"{src.preview}..."</div>
                    ) : null}
                    <div className="source-hc-footer">
                      <span className="source-hc-tier">Tier: {src.trustTier}</span>
                      <span className="source-hc-link">Click to open ↗</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
