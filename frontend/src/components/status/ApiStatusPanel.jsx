/**
 * ApiStatusPanel.jsx
 * 
 * Sidebar panel showing live health of every configured LLM provider.
 * Polls /api/status every 30s (driven by useApiStatusStore).
 * 
 * Visual states per provider:
 *   ● green    = healthy
 *   ● amber    = rate_limited / circuit_open  
 *   ✕ red      = no_credits / invalid_key / dns_error
 *   ○ grey     = no_key (not configured)
 *   ? dark     = unknown
 */

import React from 'react';
import { useApiStatusStore, STATUS_META, PROVIDER_META } from '../../store/useApiStatusStore';

function ProviderRow({ name, info }) {
  const meta = STATUS_META[info?.status] || STATUS_META.unknown;
  const display = PROVIDER_META[name] || { displayName: name, subtitle: '' };
  const retryIn = info?.retry_in_seconds;

  return (
    <div className="provider-row">
      <div className="provider-dot" style={{ color: meta.color }}>
        {meta.dot}
      </div>
      <div className="provider-info">
        <span className="provider-name">{display.displayName}</span>
        <span className="provider-subtitle">{display.subtitle}</span>
      </div>
      <div className="provider-status" style={{ color: meta.color }}>
        {retryIn && retryIn > 0 ? `${retryIn}s` : meta.label}
      </div>
    </div>
  );
}

export default function ApiStatusPanel() {
  const { providers, lastChecked, isLoading } = useApiStatusStore();

  const providerOrder = ['groq', 'gemini', 'cerebras', 'openrouter', 'tavily'];
  const hasData = Object.keys(providers).length > 0;

  return (
    <div className="api-status-panel">
      <div className="api-status-header">
        <span className="panel-label">Provider Status</span>
        {isLoading && <span className="loading-dot">⟳</span>}
        {lastChecked && !isLoading && (
          <span className="last-checked">
            {lastChecked.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>

      {!hasData && !isLoading && (
        <div className="api-status-empty">Checking providers...</div>
      )}

      {hasData && (
        <div className="provider-list">
          {providerOrder.map(name => (
            providers[name] && (
              <ProviderRow key={name} name={name} info={providers[name]} />
            )
          ))}
        </div>
      )}
    </div>
  );
}
