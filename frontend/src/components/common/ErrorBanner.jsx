/**
 * ErrorBanner.jsx
 * 
 * Replaces the old ApiError.jsx.
 * Handles ALL error types with specific, actionable messages
 * and shows which providers are broken when relevant.
 */

import React, { useState, useEffect } from 'react';
import { AlertTriangle, RefreshCw, Wifi, CreditCard, Key, Clock } from 'lucide-react';
import { useDebateStore } from '../../store/useDebateStore';
import { useApiStatusStore } from '../../store/useApiStatusStore';

const ERROR_CONFIG = {
  RATE_LIMITED: {
    icon: Clock,
    title: 'Rate Limit Reached',
    color: 'var(--amber)',
    showCountdown: true,
    showProviders: true,
  },
  NETWORK_ERROR: {
    icon: Wifi,
    title: 'Connection Lost',
    color: 'var(--con)',
    showCountdown: false,
    showProviders: false,
  },
  NO_CREDITS: {
    icon: CreditCard,
    title: 'No API Credits',
    color: 'var(--con)',
    showCountdown: false,
    showProviders: true,
  },
  INVALID_KEY: {
    icon: Key,
    title: 'Invalid API Key',
    color: 'var(--con)',
    showCountdown: false,
    showProviders: true,
  },
  SYSTEM_ERROR: {
    icon: AlertTriangle,
    title: 'System Error',
    color: 'var(--con)',
    showCountdown: false,
    showProviders: false,
  },
  VALIDATION: {
    icon: AlertTriangle,
    title: 'Invalid Claim',
    color: 'var(--amber)',
    showCountdown: false,
    showProviders: false,
  },
  TIMEOUT: {
    icon: Clock,
    title: 'Request Timed Out',
    color: 'var(--amber)',
    showCountdown: false,
    showProviders: false,
  },
};

export default function ErrorBanner() {
  const { error, reset } = useDebateStore();
  const { getErrorContext } = useApiStatusStore();
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    if (error?.type === 'RATE_LIMITED' && error?.retry_after > 0) {
      setCountdown(error.retry_after);
      const timer = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) {
            clearInterval(timer);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [error]);

  if (!error) return null;

  const cfg = ERROR_CONFIG[error.type] || ERROR_CONFIG.SYSTEM_ERROR;
  const Icon = cfg.icon;
  const providerContext = getErrorContext();

  return (
    <div className="error-banner" style={{ '--err-color': cfg.color }}>
      <div className="error-banner-header">
        <Icon size={16} className="error-icon" />
        <span className="error-title">{cfg.title}</span>
        <button className="error-dismiss" onClick={reset}>✕</button>
      </div>

      <p className="error-message">{error.message || 'An unexpected error occurred.'}</p>

      {/* Provider context — which ones are broken */}
      {cfg.showProviders && providerContext && (
        <div className="error-provider-context">
          <span className="error-context-label">Provider status:</span>
          <span className="error-context-value">{providerContext}</span>
        </div>
      )}

      {/* Countdown for rate limits */}
      {cfg.showCountdown && countdown > 0 && (
        <div className="error-countdown">
          <div className="error-countdown-bar-track">
            <div
              className="error-countdown-bar-fill"
              style={{ width: `${(countdown / (error.retry_after || 60)) * 100}%` }}
            />
          </div>
          <div className="error-countdown-label">
            Retry available in <strong>{countdown}s</strong>
          </div>
        </div>
      )}

      {countdown === 0 && error.type === 'RATE_LIMITED' && (
        <button className="error-retry-btn" onClick={reset}>
          <RefreshCw size={14} />
          Ready to retry
        </button>
      )}
    </div>
  );
}
