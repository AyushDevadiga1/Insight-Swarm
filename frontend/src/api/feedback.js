/**
 * feedback.js — /feedback endpoint
 */

import { apiClient } from './client';

export async function submitFeedback(claim, verdict, value) {
  try {
    await apiClient.post('/feedback', { claim, verdict, value });
    return true;
  } catch {
    return false;
  }
}
