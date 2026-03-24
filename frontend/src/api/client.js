/**
 * client.js — Axios base instance
 * All API modules import this for consistent base URL + error handling.
 */

import axios from 'axios';

export const apiClient = axios.create({
  baseURL: '',  // Proxied by Vite in dev (vite.config.js proxy)
  headers: { 'Content-Type': 'application/json' },
  timeout: 10_000,  // 10s for non-stream requests
});

// Response interceptor: normalise error shape
apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 429) {
      return Promise.reject({
        type: 'RATE_LIMITED',
        message: err.response.data?.detail?.message || 'Rate limited',
        retry_after: err.response.data?.detail?.retry_after ?? 60,
        provider_context: err.response.data?.detail?.provider_context || null,
      });
    }
    if (err.response?.status === 422) {
      return Promise.reject({
        type: 'VALIDATION',
        message: err.response.data?.detail || 'Invalid claim',
      });
    }
    return Promise.reject({
      type: 'SYSTEM_ERROR',
      message: err.response?.data?.detail?.message || err.message || 'Unknown error',
    });
  }
);
