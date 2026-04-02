/**
 * AgentBubble.jsx — v4
 * 🛡️ ProAgent (left, teal) vs ⚔️ ConAgent (right, red)
 * ⚖️ Moderator (centered)
 * Full-width alternating rows + Claude-style source hover cards
 */

import React from 'react';
import { useDebateStore } from '../../store/useDebateStore';

function getDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); }
  catch { return url; }
}

const TRUST_BADGE = {
  AUTHORITATIVE: { label: 'Authoritative', color: '#10b981' },
  CREDIBLE:      { label: 'Credible',       color: '#38bdf8' },
  GENERAL:       { label: 'General',        color: '#94a3b8' },
  UNKNOWN:       { label: 'Unknown',        color: '#64748b' },
};

const STATUS_ICON = {
  VERIFIED:          '✅',
  NOT_FOUND:         '❌',
  INVALID_URL:       '🚫',
  TIMEOUT:           '⏱️',
  CONTENT_MISMATCH:  '⚠️',
  PAYWALL_RESTRICTED:'🔒',
  PENDING:           '⏳',
  ERROR:             '❌',
};

/** Claude-style hover card overlaid above the source chip */
function SourceHoverCard({ src, index }) {
  const tier  = TRUST_BADGE[src.trustTier] || TRUST_BADGE.UNKNOWN;
  const icon  = STATUS_ICON[src.status]    || '⏳';
  const label = src.status === 'PENDING'
    ? 'Verifying…'
    : src.status.replace(/_/g, ' ');

  return (
    <div className="source-chip-wrap" key={index}>
      <a
        href={src.url}
        target="_blank"
        rel="noopener noreferrer"
        className={`source-chip status-${(src.status || 'pending').toLowerCase()}`}
      >
        [{index + 1}] {getDomain(src.url)}
      </a>
      {/* Hover card — shows above the chip via CSS */}
      <div className="source-hover-card">
        <div className="shc-domain">{getDomain(src.url)}</div>
        <div className="shc-row">
          <span
            className="shc-trust-badge"
            style={{ background: tier.color + '22', color: tier.color, borderColor: tier.color + '44' }}
          >
            {tier.label}
          </span>
          <span className="shc-status">
            {icon} {label}
          </span>
        </div>
        {src.error && (
          <div className="shc-error">{src.error}</div>
        )}
        <a
          href={src.url}
          target="_blank"
          rel="noopener noreferrer"
          className="shc-link-btn"
          onClick={e => e.stopPropagation()}
        >
          Open source ↗
        </a>
      </div>
    </div>
  );
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
                <SourceHoverCard key={i} src={src} index={i} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
