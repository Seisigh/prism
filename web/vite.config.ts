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
      '/api': { target: 'http://localhost:8090', changeOrigin: true },
      '/media': { target: 'http://localhost:8090', changeOrigin: true },
      '/ws': { target: 'ws://localhost:8090', ws: true },
    },
  },
})
