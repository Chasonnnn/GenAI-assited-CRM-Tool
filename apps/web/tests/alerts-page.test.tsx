import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AlertsPage from '../app/(app)/settings/alerts/page'

const mockUseAlerts = vi.fn()
const mockResolve = vi.fn()

vi.mock('@/lib/hooks/use-ops', () => ({
    useAlerts: (params: any) => mockUseAlerts(params),
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
                        alert_type: 'meta_fetch_failed',
                        severity: 'critical',
                        status: 'open',
                        title: 'Meta lead fetch failing',
                        message: 'Token expired',
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
    })

    it('renders an alert and can resolve it', () => {
        render(<AlertsPage />)
        expect(screen.getByText('Alerts')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /resolve/i }))
        expect(mockResolve).toHaveBeenCalledWith('a1')
    })
})
