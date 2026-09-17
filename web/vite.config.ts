import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  envDir: '../', // read the repo-root .env, not web/.env
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8010', changeOrigin: true },
      '/media': { target: 'http://localhost:8010', changeOrigin: true },
      '/ws': { target: 'ws://localhost:8010', ws: true },
    },
  },
})
