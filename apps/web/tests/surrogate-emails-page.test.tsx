import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import SurrogateEmailsPage from '../app/(app)/surrogates/[id]/emails/page'
import { ApiError } from '@/lib/api'

const mockUseSurrogateEmails = vi.fn()
const mockUseSurrogateEmailContacts = vi.fn()
const permissionState = { granted: [] as string[] }

vi.mock('next/navigation', () => ({
    useParams: () => ({ id: 's1' }),
}))

vi.mock('next/link', () => ({
    default: ({ href, children, ...props }: { href: string; children?: ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock('@/components/app-link', () => ({
    default: ({ href, children, ...props }: { href: string; children?: ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock('@/lib/hooks/use-permission-check', () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => permissionState.granted.includes(permission),
    }),
}))

vi.mock('@/lib/hooks/use-surrogate-emails', () => ({
    useSurrogateEmails: (surrogateId: string, options: unknown) => mockUseSurrogateEmails(surrogateId, options),
    useSurrogateEmailContacts: (surrogateId: string, options: unknown) =>
        mockUseSurrogateEmailContacts(surrogateId, options),
    useCreateSurrogateEmailContact: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeactivateSurrogateEmailContact: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function queryResult(overrides: Record<string, unknown> = {}) {
    return {
        data: { items: [] },
        isLoading: false,
        isError: false,
        error: null,
        isFetching: false,
        refetch: vi.fn(),
        ...overrides,
    }
}

describe('SurrogateEmailsPage', () => {
    beforeEach(() => {
        permissionState.granted = ['view_tickets']
        mockUseSurrogateEmails.mockReset()
        mockUseSurrogateEmailContacts.mockReset()
        mockUseSurrogateEmails.mockReturnValue(queryResult())
        mockUseSurrogateEmailContacts.mockReturnValue(queryResult())
    })

    it('shows a permission state and sends no requests without view_tickets', () => {
        permissionState.granted = []

        render(<SurrogateEmailsPage />)

        expect(screen.getByRole('heading', { name: 'No access to emails' })).toBeInTheDocument()
        expect(screen.getByRole('link', { name: 'Back to Overview' })).toHaveAttribute('href', '/surrogates/s1')
        expect(screen.queryByText('No linked ticket emails yet.')).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Add Contact' })).not.toBeInTheDocument()
        expect(mockUseSurrogateEmails).toHaveBeenCalledWith('s1', { enabled: false })
        expect(mockUseSurrogateEmailContacts).toHaveBeenCalledWith('s1', { enabled: false })
    })

    it('shows a load error with retry, not the empty state or the raw error', () => {
        mockUseSurrogateEmails.mockReturnValue(
            queryResult({
                data: undefined,
                isError: true,
                error: new ApiError(500, 'Internal Server Error', 'db timeout on tickets'),
            }),
        )

        render(<SurrogateEmailsPage />)

        expect(screen.getByText("Couldn't load emails")).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
        expect(screen.queryByText('No linked ticket emails yet.')).not.toBeInTheDocument()
        expect(screen.queryByText(/db timeout/)).not.toBeInTheDocument()
    })

    it('labels the contact inputs and maps stored contact values to labels', () => {
        mockUseSurrogateEmailContacts.mockReturnValue(
            queryResult({
                data: {
                    items: [
                        {
                            id: 'c1',
                            surrogate_id: 's1',
                            email: 'jane@example.com',
                            email_domain: 'example.com',
                            source: 'system',
                            label: 'Primary',
                            contact_type: 'surrogate',
                            is_active: true,
                            created_by_user_id: null,
                            created_at: '2026-01-01T00:00:00Z',
                            updated_at: '2026-01-01T00:00:00Z',
                        },
                    ],
                },
            }),
        )

        render(<SurrogateEmailsPage />)

        expect(screen.getByLabelText('Email')).toBeInTheDocument()
        expect(screen.getByLabelText('Label')).toBeInTheDocument()
        expect(screen.getByLabelText('Type')).toBeInTheDocument()
        expect(screen.getByText('System • Primary • Surrogate')).toBeInTheDocument()
        expect(screen.queryByText(/system • Primary • surrogate/)).not.toBeInTheDocument()
    })
})
