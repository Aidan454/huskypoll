import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      // Reliable file watching when the source is a bind mount (Windows/WSL).
      usePolling: true,
    },
  },
})
