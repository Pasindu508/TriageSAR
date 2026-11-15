import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

const apiTarget = process.env.TRIAGESAR_API_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  // A sub-path such as /TriageSAR/ when hosted on GitHub Pages; the API-backed build uses /.
  base: process.env.VITE_BASE ?? '/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': apiTarget, '/health': apiTarget },
  },
  worker: { format: 'es' },
  build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 1500 },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
});
