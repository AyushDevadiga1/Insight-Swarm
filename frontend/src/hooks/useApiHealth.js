/**
 * useApiHealth.js
 * 
 * Starts the API status polling on app mount and tears it down on unmount.
 * Usage: call once at the top level of App.jsx
 */

import { useEffect } from 'react';
import { useApiStatusStore } from '../store/useApiStatusStore';

export function useApiHealth() {
  const { startPolling, stopPolling } = useApiStatusStore();
  
  useEffect(() => {
    startPolling();
    return () => stopPolling();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}
