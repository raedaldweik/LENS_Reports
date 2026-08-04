import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev: Vite on :5173 proxies /api to the FastAPI backend.
// Backend port defaults to 8000 — override with VITE_API_PORT (or a full
// VITE_API_TARGET URL) if something else is already running there.
// Prod: the backend serves the built dist/ same-origin, so no proxy is involved.
const target = process.env.VITE_API_TARGET
  || `http://127.0.0.1:${process.env.VITE_API_PORT || 8000}`;

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target,
        changeOrigin: true,
      },
    },
  },
});
