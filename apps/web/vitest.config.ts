import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
    plugins: [react()],
    test: {
        environment: 'jsdom',
        // Keep fresh globals per file; the shared location mock is not VM-compatible.
        pool: 'forks',
        isolate: true,
        fsModuleCache: true,
        globals: true,
        alias: {
            '@': path.resolve(__dirname, './'),
        },
        // Shared browser polyfills and cleanup.
        setupFiles: ['./tests/setup.ts'],
        exclude: [
            '**/node_modules/**',
            '**/dist/**',
        ],
    },
})
