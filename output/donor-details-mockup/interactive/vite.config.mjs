import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/postcss';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(root, '../../../apps/web');
export default defineConfig({
  resolve: {
    alias: [
      { find: '@/components/app-link', replacement: path.join(root, 'src/LocalLink.tsx') },
      { find: '@', replacement: web },
    ],
    dedupe: ['react', 'react-dom'],
  },
  css: { postcss: { plugins: [tailwindcss()] } },
  build: { outDir: 'dist/client', chunkSizeWarningLimit: 2500 },
  optimizeDeps: { include: ['react', 'react-dom/client'] },
  server: { host: '127.0.0.1', port: 3047, strictPort: true, fs: { allow: [root, web] } },
  plugins: [react()],
});
