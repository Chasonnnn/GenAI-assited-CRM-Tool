import { expect, afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom/matchers'
import '@testing-library/jest-dom'

expect.extend(matchers)

afterEach(() => {
    cleanup()
})

// ----------------------------------------------------------------------------
// JSDOM polyfills for UI libs (Base UI, charts, etc.)
// ----------------------------------------------------------------------------

Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(), // deprecated
        removeListener: vi.fn(), // deprecated
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    }),
})

class MockResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
}

// @ts-expect-error - test environment polyfill
globalThis.ResizeObserver = globalThis.ResizeObserver ?? MockResizeObserver

class MockIntersectionObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
}

// @ts-expect-error - test environment polyfill
globalThis.IntersectionObserver = globalThis.IntersectionObserver ?? MockIntersectionObserver

// Clipboard is used in Case Detail page.
Object.defineProperty(navigator, 'clipboard', {
    value: navigator.clipboard ?? {
        writeText: vi.fn(),
    },
})
