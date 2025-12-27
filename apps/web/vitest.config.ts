import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
    plugins: [react()],
    test: {
        environment: 'jsdom',
        globals: true,
        alias: {
            '@': path.resolve(__dirname, './'),
        },
        // Default: unit tests with global mocks
        setupFiles: ['./tests/setup.ts'],
        // Exclude integration tests from default run
        exclude: [
            '**/node_modules/**',
            '**/dist/**',
            '**/integration/**',
        ],
    },
})
