import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/verify': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/feedback': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/api/status': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // SSE endpoint — disable buffering so events flow immediately
      '/stream': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (_proxyRes, _req, res) => {
            // Tell Nginx/Vite not to buffer this response
            res.setHeader('Cache-Control', 'no-cache')
            res.setHeader('X-Accel-Buffering', 'no')
          })
        },
      },
    }
  }
})

