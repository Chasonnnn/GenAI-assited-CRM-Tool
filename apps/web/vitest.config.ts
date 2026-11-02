import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
    plugins: [react()],
    test: {
        environment: 'jsdom',
        // The shared location mock is not VM-compatible. Workers reuse one environment and the
        // dependency module cache; tests/reset-file-state.ts restores per-file state.
        pool: 'forks',
        isolate: false,
        fsModuleCache: true,
        globals: true,
        alias: {
            '@': path.resolve(__dirname, './'),
        },
        // Per-file state reset, then shared browser polyfills and cleanup.
        setupFiles: ['./tests/reset-file-state.ts', './tests/setup.ts'],
        coverage: {
            provider: 'v8',
            include: [
                'app/**/*.{ts,tsx}',
                'components/**/*.{ts,tsx}',
                'hooks/**/*.{ts,tsx}',
                'lib/**/*.{ts,tsx}',
                'proxy.ts',
                'instrumentation-client.ts',
                'next.config.js',
            ],
            exclude: ['**/*.d.ts'],
            reporter: ['text-summary', 'json-summary', 'json'],
            thresholds: {
                lines: 62.07,
                statements: 60.04,
                branches: 57.05,
                functions: 52.11,
            },
        },
        exclude: [
            '**/node_modules/**',
            '**/dist/**',
        ],
    },
})
