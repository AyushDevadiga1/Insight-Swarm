import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/verify': 'http://127.0.0.1:8000',
      '/feedback': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/api/status': 'http://127.0.0.1:8000',
      '/stream': 'http://127.0.0.1:8000',
    }
  }
})
