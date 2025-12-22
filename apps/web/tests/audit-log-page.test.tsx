import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AuditLogPage from '../app/(app)/settings/audit/page'

const mockUseAuditLogs = vi.fn()
const mockUseAuditExports = vi.fn()
const mockCreateExport = vi.fn()
const mockRefetchExports = vi.fn()

vi.mock('@/lib/hooks/use-audit', () => ({
    useAuditLogs: (filters: any) => mockUseAuditLogs(filters),
    useEventTypes: () => ({ data: ['user_login', 'pipeline_updated'] }),
    useAuditExports: () => mockUseAuditExports(),
    useCreateAuditExport: () => ({ mutateAsync: mockCreateExport, isPending: false }),
    useAIAuditActivity: () => ({
        data: {
            counts: {
                ai_action_approved: 0,
                ai_action_rejected: 0,
                ai_action_failed: 0,
                ai_action_denied: 0,
            },
            recent: [],
        },
        isLoading: false,
    }),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { role: 'admin' } }),
}))

describe('AuditLogPage', () => {
    beforeEach(() => {
        mockUseAuditLogs.mockReturnValue({
            data: {
                items: [
                    {
                        id: 'e1',
                        event_type: 'user_login',
                        actor_user_id: 'u1',
                        actor_name: 'Alice',
                        target_type: null,
                        target_id: null,
                        details: null,
                        ip_address: '127.0.0.1',
                        created_at: new Date().toISOString(),
                    },
                ],
                total: 40,
                page: 1,
                per_page: 20,
            },
            isLoading: false,
        })
        mockUseAuditExports.mockReturnValue({ data: { items: [] }, refetch: mockRefetchExports })
    })

    it('renders audit entries and supports pagination', () => {
        render(<AuditLogPage />)

        expect(screen.getByText('Audit Log')).toBeInTheDocument()
        expect(screen.getByText('Activity Log')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        expect(mockUseAuditLogs).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, per_page: 20 }))
    })
})
