import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://localhost:8000',
      '/config': 'http://localhost:8000',
      '/projects': 'http://localhost:8000',
      '/agents': 'http://localhost:8000',
      '/events': 'http://localhost:8000',
      '/hermes': 'http://localhost:8000',
      '/tool-gateway': 'http://localhost:8000',
      '/mnemosyne': 'http://localhost:8000',
      '/angelia': 'http://localhost:8000',
      '/hestia': 'http://localhost:8000',
      '/oracle': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
    }
  }
})
