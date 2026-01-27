import type { MouseEvent } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent, screen } from '@testing-library/react'
import AppLink from '@/components/app-link'

const mockPush = vi.fn()
const mockReplace = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush, replace: mockReplace }),
}))

vi.mock('next/link', () => ({
    default: ({ href, children, ...props }: { href: string | { pathname?: string }; children: React.ReactNode }) => (
        <a href={typeof href === 'string' ? href : href?.pathname ?? ''} {...props}>
            {children}
        </a>
    ),
}))

beforeEach(() => {
    mockPush.mockClear()
    mockReplace.mockClear()
})

describe('AppLink', () => {
    it('navigates via router by default even if click is prevented upstream', () => {
        const onClick = vi.fn((event: MouseEvent<HTMLAnchorElement>) => {
            event.preventDefault()
        })
        render(
            <AppLink href="/surrogates" onClick={onClick}>
                Go
            </AppLink>
        )

        fireEvent.click(screen.getByRole('link', { name: 'Go' }))

        expect(onClick).toHaveBeenCalled()
        expect(mockPush).toHaveBeenCalledWith('/surrogates', undefined)
        expect(mockReplace).not.toHaveBeenCalled()
    })

    it('respects fallbackMode="none"', () => {
        const onClick = vi.fn((event: MouseEvent<HTMLAnchorElement>) => {
            event.preventDefault()
        })
        render(
            <AppLink href="/surrogates" fallbackMode="none" onClick={onClick}>
                Go
            </AppLink>
        )

        fireEvent.click(screen.getByRole('link', { name: 'Go' }))

        expect(mockPush).not.toHaveBeenCalled()
        expect(mockReplace).not.toHaveBeenCalled()
    })
})
