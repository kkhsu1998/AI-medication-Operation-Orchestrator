import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy: forward API + health calls to the FastAPI backend so the browser
// talks to Vite (5173) with no CORS setup. Override the target with API_TARGET.
const API_TARGET = process.env.API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
      '/health': { target: API_TARGET, changeOrigin: true },
    },
  },
})
