import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // Prefer 5173; if busy (other Vite apps), Vite picks next free port.
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': {
        // 8100 = dashboard API (8000 often taken by other local projects)
        target: 'http://localhost:8100',
        changeOrigin: true,
      },
    },
  },
})
