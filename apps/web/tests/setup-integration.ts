/**
 * Integration Test Setup
 * 
 * Use this setup file for tests that need real API mocking with MSW.
 * Add this to vitest.config.ts as a separate project for integration tests.
 */

import { beforeAll, afterEach, afterAll, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom'
import { server } from './mocks/server'

// Start MSW server before all tests
beforeAll(() => {
    server.listen({ onUnhandledRequest: 'warn' })
})

// Reset handlers after each test (important for test isolation)
afterEach(() => {
    server.resetHandlers()
    cleanup()
})

// Close server after all tests
afterAll(() => {
    server.close()
})

// ----------------------------------------------------------------------------
// JSDOM polyfills (same as unit test setup)
// ----------------------------------------------------------------------------

Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    }),
})

class MockResizeObserver {
    observe() { }
    unobserve() { }
    disconnect() { }
}

// @ts-expect-error - test environment polyfill
globalThis.ResizeObserver = globalThis.ResizeObserver ?? MockResizeObserver

class MockIntersectionObserver {
    observe() { }
    unobserve() { }
    disconnect() { }
}

// @ts-expect-error - test environment polyfill
globalThis.IntersectionObserver = globalThis.IntersectionObserver ?? MockIntersectionObserver

Object.defineProperty(navigator, 'clipboard', {
    value: navigator.clipboard ?? { writeText: vi.fn() },
})

if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = vi.fn()
}

if (!Element.prototype.getAnimations) {
    // @ts-expect-error - minimal Web Animations API polyfill
    Element.prototype.getAnimations = () => []
}
