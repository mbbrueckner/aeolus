import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // The API runs as a separate FastAPI process during development.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
