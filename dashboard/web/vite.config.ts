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
        // Use 127.0.0.1 — on Windows, localhost can resolve to ::1 and break
        // Docker port maps → proxy ECONNRESET → Vite serves index.html →
        // frontend JSON.parse fails with Unexpected token '<!doctype'.
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
    },
  },
})
