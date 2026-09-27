import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ApiError } from '@/lib/api'
import AlertsPage from '../app/(app)/settings/alerts/page'

const mockUseAlerts = vi.fn()
const mockResolve = vi.fn()
const mockCan = vi.fn()

vi.mock('@/lib/hooks/use-permission-check', () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => mockCan(permission),
    }),
}))

vi.mock('@/components/app-link', () => ({
    default: ({ children, href, ...props }: React.ComponentProps<'a'>) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock('@/lib/hooks/use-ops', () => ({
    useAlerts: (params: unknown) => mockUseAlerts(params),
    useAlertsSummary: () => ({ data: { critical: 1, error: 0, warn: 0 } }),
    useResolveAlert: () => ({ mutate: mockResolve, isPending: false }),
    useAcknowledgeAlert: () => ({ mutate: vi.fn(), isPending: false }),
    useSnoozeAlert: () => ({ mutate: vi.fn(), isPending: false }),
}))

describe('AlertsPage', () => {
    beforeEach(() => {
        mockUseAlerts.mockReturnValue({
            data: {
                items: [
                    {
                        id: 'a1',
                        alert_type: 'surrogate_number_counter_drift',
                        severity: 'critical',
                        status: 'open',
                        title: 'Surrogate number counter drift repaired',
                        message: 'The counter was repaired before retrying surrogate creation.',
                        integration_key: null,
                        occurrence_count: 1,
                        first_seen_at: new Date().toISOString(),
                        last_seen_at: new Date().toISOString(),
                        resolved_at: null,
                    },
                ],
                total: 1,
            },
            isLoading: false,
        })
        mockResolve.mockReset()
        mockCan.mockReset()
        mockCan.mockImplementation((permission: string) => permission === 'manage_ops')
    })

    it('renders an alert and can resolve it', () => {
        render(<AlertsPage />)
        expect(screen.getByRole('heading', { level: 1, name: 'System Alerts' })).toBeInTheDocument()
        expect(screen.getByText('Surrogate Number Counter Drift')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /resolve/i }))
        expect(mockResolve).toHaveBeenCalledWith('a1')
    })

    it('shows the denied state instead of an all-clear list without manage_ops', () => {
        mockCan.mockReturnValue(false)
        mockUseAlerts.mockClear()

        render(<AlertsPage />)

        expect(screen.getByText('Permission required')).toBeInTheDocument()
        expect(screen.queryByText(/All systems operating normally/)).not.toBeInTheDocument()
        expect(mockUseAlerts).not.toHaveBeenCalled()
    })

    it('shows a load error instead of the empty state when alerts fail to load', () => {
        mockUseAlerts.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(500, 'Internal Server Error', 'boom'),
            isFetching: false,
            refetch: vi.fn(),
        })

        render(<AlertsPage />)

        expect(screen.getByText("Couldn't load alerts")).toBeInTheDocument()
        expect(screen.queryByText(/All systems operating normally/)).not.toBeInTheDocument()
    })
})
