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

        {/* Sources cited — progressive disclosure */}
        {sources.length > 0 && !isStreaming && (
          <details className="agent-sources">
            <summary className="agent-sources-toggle">
              {sources.length} source{sources.length !== 1 ? 's' : ''} cited
            </summary>
            <div className="agent-sources-list">
              {sources.map((url, i) => (
                <a
                  key={i}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="agent-source-link"
                >
                  {url}
                </a>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
