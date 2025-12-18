import { describe, it, expect, vi } from 'vitest'

const mockRedirect = vi.fn()

vi.mock('next/navigation', () => ({
    redirect: (path: string) => mockRedirect(path),
}))

import Home from '../app/page'

describe('Home redirect', () => {
    it('redirects / to /dashboard', () => {
        Home()
        expect(mockRedirect).toHaveBeenCalledWith('/dashboard')
    })
})

