import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react()],
  // Relative asset paths so one build works under any path prefix (see Backend README).
  base: command === 'build' ? './' : '/',
  server: {
    // Without VITE_API_BASE, the app calls /api on this server and Vite forwards it
    // (live updates included) to the backend on port 8000.
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true, ws: true },
    },
    watch: {
      // Reliable file watching when the source is a bind mount (Windows/WSL).
      usePolling: true,
    }
  },
}));
