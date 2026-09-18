import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  envDir: '../', // read the repo-root .env, not web/.env
  resolve: {
    alias: {
      // sdk/ is TypeScript source, not a published package — Vite
      // bundles it straight from source rather than requiring a build
      // step, since both packages live in this one repo.
      '@prism/sdk': path.resolve(import.meta.dirname, '../sdk/src/index.ts'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // ws: true is required here too, not just below -- the admin
      // console's live view WebSocket lives at /api/admin/live/{id},
      // and without it Vite proxies the request as plain HTTP and the
      // upgrade never happens: the socket sits in CONNECTING forever
      // with no error, which is a real bug found live (Live view showed
      // "Disconnected" for every session, always, with no exception).
      '/api': { target: 'http://localhost:8090', changeOrigin: true, ws: true },
      '/media': { target: 'http://localhost:8090', changeOrigin: true },
      '/ws': { target: 'ws://localhost:8090', ws: true },
    },
  },
})
