/**
 * health.js — /api/status endpoint
 */

import { apiClient } from './client';

export async function getProviderStatus() {
  const res = await apiClient.get('/api/status');
  return res.data;
}
