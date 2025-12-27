/**
 * Vitest config for Integration Tests
 * 
 * Uses MSW for real API mocking instead of global mocks.
 * Run with: pnpm test:integration
 */

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
        // Integration test setup with MSW
        setupFiles: ['./tests/setup-integration.ts'],
        // Only run integration tests
        include: ['**/integration/**/*.test.{ts,tsx}'],
    },
})
