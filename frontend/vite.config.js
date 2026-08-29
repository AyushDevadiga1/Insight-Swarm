import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'

// Backend target is env-overridable: VITE_API_TARGET (defaults to local dev backend)
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/verify': {
          target,
          changeOrigin: true,
        },
        '/feedback': {
          target,
          changeOrigin: true,
        },
        '/health': {
          target,
          changeOrigin: true,
        },
        // All /api/* routes → backend (covers /api/status, /api/debate/resume/:id)
        '/api': {
          target,
          changeOrigin: true,
        },
        // WebSocket for HITL
        '/ws': {
          target,
          changeOrigin: true,
          ws: true,
        },
        // SSE endpoint — disable buffering so events flow immediately
        '/stream': {
          target,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on('proxyRes', (_proxyRes, _req, res) => {
              res.setHeader('Cache-Control', 'no-cache')
              res.setHeader('X-Accel-Buffering', 'no')
            })
          },
        },
      }
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            // Split Vendors out of main bundle so the UI loads fast
            'zustand': ['zustand'],
            'lucide': ['lucide-react'],
          },
        },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      include: ['src/**/*.{test,spec}.{js,jsx}'],
      setupFiles: ['./src/test/setup.js'],
    },
  }
})
