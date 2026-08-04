import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: process.env.BIND_HOST || '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: `http://${process.env.BIND_HOST || '127.0.0.1'}:8888`,
        changeOrigin: true,
      },
      '/thumbs': {
        target: `http://${process.env.BIND_HOST || '127.0.0.1'}:8888`,
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: process.env.BIND_HOST || '127.0.0.1',
    port: 4173,
    proxy: {
      '/api': {
        target: `http://${process.env.BIND_HOST || '127.0.0.1'}:8888`,
        changeOrigin: true,
      },
      '/thumbs': {
        target: `http://${process.env.BIND_HOST || '127.0.0.1'}:8888`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    // The project folder is mounted with delete/rename disabled in some agent
    // sandboxes; emptyOutDir defaults to wiping dist/ before each build, which
    // fails there. Old hashed chunks just accumulate as harmless orphans instead.
    emptyOutDir: false,
  },
})
