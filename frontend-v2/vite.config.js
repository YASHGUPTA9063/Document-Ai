import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Mirrors the nginx /api/ proxy used in the Docker build so the same
    // relative VITE_API_BASE_URL works in dev and in production.
    //
    // Straight passthrough — no rewrite. The backend serves /api/v1/* itself;
    // stripping the prefix here would 404 every request.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
