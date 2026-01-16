import type { ReactNode } from "react"
import { expect, afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom/matchers'
import '@testing-library/jest-dom'

// Mock React Query
vi.mock('@tanstack/react-query', () => ({
    useQuery: vi.fn(() => ({
        data: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
    })),
    useMutation: vi.fn(() => ({
        mutateAsync: vi.fn(),
        isPending: false,
        error: null,
    })),
    useQueryClient: vi.fn(() => ({
        invalidateQueries: vi.fn(),
        setQueryData: vi.fn(),
        getQueryData: vi.fn(),
        removeQueries: vi.fn(),
    })),
    QueryClient: vi.fn(() => ({})),
    QueryClientProvider: ({ children }: { children: ReactNode }) => children,
}))

vi.mock('@/lib/context/ai-context', () => ({
    AIContextProvider: ({ children }: { children: ReactNode }) => children,
    useAIContext: () => ({
        entityType: null,
        entityId: null,
        entityName: null,
        isOpen: false,
        togglePanel: vi.fn(),
        openPanel: vi.fn(),
        closePanel: vi.fn(),
        setContext: vi.fn(),
        clearContext: vi.fn(),
        canUseAI: false,
        isAIEnabled: false,
    }),
    useSetAIContext: () => {},
}))

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

// Clipboard is used in Surrogate Detail page.
Object.defineProperty(navigator, 'clipboard', {
    value: navigator.clipboard ?? {
        writeText: vi.fn(),
    },
})

// JSDOM doesn't implement scrollIntoView (used in AI Assistant).
if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = vi.fn()
}

// Base UI ScrollArea uses getAnimations() for smooth updates.
if (!Element.prototype.getAnimations) {
    // @ts-expect-error - minimal Web Animations API polyfill for tests
    Element.prototype.getAnimations = () => []
}

// JSDOM navigation stubs to avoid "Not implemented: navigation" warnings.
const noopNavigate = vi.fn()
try {
    Object.defineProperty(window.location, 'assign', { configurable: true, value: noopNavigate })
    Object.defineProperty(window.location, 'replace', { configurable: true, value: noopNavigate })
    Object.defineProperty(window.location, 'reload', { configurable: true, value: noopNavigate })
} catch {
    Object.defineProperty(window, 'location', {
        writable: true,
        value: {
            href: window.location.href,
            origin: window.location.origin,
            protocol: window.location.protocol,
            host: window.location.host,
            hostname: window.location.hostname,
            port: window.location.port,
            pathname: window.location.pathname,
            search: window.location.search,
            hash: window.location.hash,
            ancestorOrigins: window.location.ancestorOrigins,
            assign: noopNavigate,
            replace: noopNavigate,
            reload: noopNavigate,
        },
    })
}
