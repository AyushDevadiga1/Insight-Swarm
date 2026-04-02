/**
 * ApiStatusPanel.jsx — v3
 * Shows each provider with dot + name + fill bar + % label
 */

import React from 'react';
import { useApiStatusStore, STATUS_META, PROVIDER_META } from '../../store/useApiStatusStore';

const STATUS_COLOR = {
  healthy:      'var(--pro)',
  rate_limited: 'var(--warning)',
  circuit_open: 'var(--warning)',
  no_credits:   'var(--danger)',
  invalid_key:  'var(--danger)',
  dns_error:    'var(--danger)',
  no_key:       'var(--text-4)',
  unknown:      'var(--text-4)',
};

const STATUS_BAR_PCT = {
  healthy:      100,
  rate_limited: 20,
  circuit_open: 30,
  no_credits:   0,
  invalid_key:  0,
  dns_error:    0,
  no_key:       0,
  unknown:      0,
};

function ProviderRow({ name, info }) {
  const status  = info?.status || 'unknown';
  const color   = STATUS_COLOR[status] || 'var(--text-4)';
  const barPct  = STATUS_BAR_PCT[status] ?? 0;
  const display = PROVIDER_META[name] || { displayName: name, subtitle: '' };
  const meta    = STATUS_META[status] || STATUS_META.unknown;
  const retryIn = info?.retry_in_seconds;

  return (
    <div className="provider-row">
      <div className="provider-dot" style={{ color }}>{meta.dot}</div>
      <div className="provider-info">
        <span className="provider-name">{display.displayName}</span>
        <span className="provider-subtitle">{display.subtitle}</span>
      </div>
      <div className="provider-bar-wrap">
        <div
          className="provider-bar-fill"
          style={{ width: `${barPct}%`, background: color }}
        />
      </div>
      <div className="provider-status" style={{ color }}>
        {retryIn && retryIn > 0 ? `${retryIn}s` : meta.label.split(' ')[0]}
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
        <span className="panel-label">API health</span>
        {isLoading && <span className="loading-dot">⟳</span>}
        {lastChecked && !isLoading && (
          <span className="last-checked">
            {lastChecked.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>

      {!hasData && !isLoading && (
        <div className="api-status-empty">Checking providers…</div>
      )}

      {hasData && (
        <div className="provider-list">
          {providerOrder.map(name =>
            providers[name] ? (
              <ProviderRow key={name} name={name} info={providers[name]} />
            ) : null
          )}
        </div>
      )}
    </div>
  );
}
