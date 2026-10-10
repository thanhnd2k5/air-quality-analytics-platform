import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // Prefer free port away from other local Vite apps (often 5173/5174).
    port: 5180,
    strictPort: false,
    proxy: {
      // Fallback if VITE_API_BASE_URL is empty; .env.development points at :8100 directly.
      '/api': {
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
    },
  },
})
