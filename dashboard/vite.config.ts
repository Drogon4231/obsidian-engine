import { defineConfig } from 'vite'
import preact from '@preact/preset-vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [preact(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
      '/stream': {
        target: 'http://localhost:8080',
        headers: { 'X-Accel-Buffering': 'no' },
      },
      '/trigger': 'http://localhost:8080',
      '/kill': 'http://localhost:8080',
      '/queue': 'http://localhost:8080',
      '/music': 'http://localhost:8080',
      '/trends': 'http://localhost:8080',
      '/audit': 'http://localhost:8080',
      '/schedule': 'http://localhost:8080',
      '/history': 'http://localhost:8080',
      '/status': 'http://localhost:8080',
      '/costs': 'http://localhost:8080',
      '/login': {
        target: 'http://localhost:8080',
        cookieDomainRewrite: 'localhost',
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/mocks/server.ts'],
    globals: true,
  },
})
