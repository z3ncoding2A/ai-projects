import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    host: process.env.BIND_HOST || '100.116.128.90',
    port: 5173,
    proxy: {
      '/api': {
        target: `http://${process.env.BIND_HOST || '100.116.128.90'}:8888`,
        changeOrigin: true,
      },
      '/thumbs': {
        target: `http://${process.env.BIND_HOST || '100.116.128.90'}:8888`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
