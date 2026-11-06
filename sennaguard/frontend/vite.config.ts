import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/sennaguard/', // no servidor o Apache publica a aplicação em https://<servidor>/sennaguard/
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/sennaguard/api': { target: 'http://127.0.0.1:8000', rewrite: p => p.replace(/^\/sennaguard/, '') } } },
})
