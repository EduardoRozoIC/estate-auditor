import { defineConfig } from 'vite';

// La app activa usa vanilla JS (index.html → js/app.js).
// NO se necesita el plugin React para eso.
export default defineConfig({
  plugins: [],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
});
