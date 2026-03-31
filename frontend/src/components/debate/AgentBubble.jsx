/**
 * AgentBubble.jsx — v3
 * 🛡️ ProAgent (left, teal) vs ⚔️ ConAgent (right, red)
 * ⚖️ Moderator (centered)
 * Full-width alternating rows instead of side-by-side columns
 */

import React from 'react';
import { useDebateStore } from '../../store/useDebateStore';

function getDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); }
  catch { return url; }
}

const AGENT_META = {
  PRO: {
    label:    'ProAgent',
    icon:     '🛡️',
    rowClass: 'msg-pro',
    avatarClass: 'msg-avatar-pro',
    badgeClass:  'msg-badge-pro',
  },
  CON: {
    label:    'ConAgent',
    icon:     '⚔️',
    rowClass: 'msg-con',
    avatarClass: 'msg-avatar-con',
    badgeClass:  'msg-badge-con',
  },
  MODERATOR: {
    label:    'Moderator',
    icon:     '⚖️',
    rowClass: 'msg-mod',
    avatarClass: 'msg-avatar-mod',
    badgeClass:  'msg-badge-mod',
  },
  FACT: {
    label:    'FactChecker',
    icon:     '🔬',
    rowClass: 'msg-pro',
    avatarClass: 'msg-avatar-fact',
    badgeClass:  'msg-badge-fact',
  },
};

export default function AgentBubble({ agent, round, text, isStreaming, sources = [] }) {
  const meta = AGENT_META[agent] || AGENT_META.PRO;
  const isEmpty = !text;
  const sourceResults = useDebateStore(state => state.sourceResults || []);

  const enrichedSources = sources.map(url => {
    const verifiedData = sourceResults.find(r => r.url === url);
    return {
      url,
      domain:     getDomain(url),
      status:     verifiedData?.status || 'PENDING',
      trustTier:  verifiedData?.trust_tier || 'UNKNOWN',
      preview:    verifiedData?.content_preview || null,
      error:      verifiedData?.error || null,
    };
  });

  return (
    <div className={`msg-row ${meta.rowClass} animate-fade-up`}>
      <div className={`msg-avatar ${meta.avatarClass}`}>
        {meta.icon}
      </div>

      <div className="msg-body">
        <div className="msg-meta">
          <span className="msg-name">{meta.label}</span>
          {round && (
            <span className={`msg-badge ${meta.badgeClass}`}>
              Rd {round} · {agent === 'PRO' ? 'supporting' : agent === 'CON' ? 'rebuttal' : 'analysis'}
            </span>
          )}
          {isStreaming && (
            <span className="msg-streaming-badge">● live</span>
          )}
        </div>

        <div className="msg-text">
          {isEmpty && isStreaming ? (
            <span className="thinking-dots">
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

        {enrichedSources.length > 0 && !isStreaming && (
          <div className="agent-sources-chips-container">
            <div className="agent-sources-label">Sources</div>
            <div className="agent-sources-chips">
              {enrichedSources.map((src, i) => (
                <a
                  key={i}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`source-chip status-${src.status.toLowerCase()}`}
                >
                  [{i + 1}] {src.domain}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
