/**
 * vite.config.js — proxies /verify, /stream, /api, /feedback to the FastAPI backend
 * Copy this to frontend/vite.config.js
 */

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/verify':   { target: 'http://localhost:8000', changeOrigin: true },
      '/feedback': { target: 'http://localhost:8000', changeOrigin: true },
      '/stream':   { target: 'http://localhost:8000', changeOrigin: true },
      '/api':      { target: 'http://localhost:8000', changeOrigin: true },
      '/health':   { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Split Zustand out of main bundle so the UI loads fast
          'zustand': ['zustand'],
          'lucide':  ['lucide-react'],
        },
      },
    },
  },
});
