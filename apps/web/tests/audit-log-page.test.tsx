import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ApiError } from '@/lib/api'
import AuditLogPage from '../app/(app)/settings/audit/page'

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

const mockUseAuditLogs = vi.fn()
const mockUseAuditExports = vi.fn()
const mockCreateExport = vi.fn()
const mockRefetchExports = vi.fn()

vi.mock('@/lib/hooks/use-audit', () => ({
    useAuditLogs: (filters: unknown) => mockUseAuditLogs(filters),
    useEventTypes: () => ({ data: ['user_login', 'pipeline_updated'] }),
    useAuditExports: (options: unknown) => mockUseAuditExports(options),
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
        mockCan.mockReset()
        mockCan.mockImplementation((permission: string) => permission === 'view_audit_log')
    })

    it('shows the denied state without the export form or entries without view_audit_log', () => {
        mockCan.mockReturnValue(false)
        mockUseAuditLogs.mockClear()

        render(<AuditLogPage />)

        expect(screen.getByRole('heading', { level: 1, name: 'Audit Log' })).toBeInTheDocument()
        expect(screen.getByText('Permission required')).toBeInTheDocument()
        expect(screen.queryByText('Activity Log')).not.toBeInTheDocument()
        expect(mockUseAuditLogs).not.toHaveBeenCalled()
    })

    it('shows a load error instead of an empty log when entries fail to load', () => {
        mockUseAuditLogs.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(500, 'Internal Server Error', 'boom'),
            isFetching: false,
            refetch: vi.fn(),
        })

        render(<AuditLogPage />)

        expect(screen.getByText("Couldn't load audit log")).toBeInTheDocument()
        expect(screen.queryByText(/No audit log entries/i)).not.toBeInTheDocument()
    })

    it('renders audit entries and supports pagination', () => {
        render(<AuditLogPage />)

        expect(screen.getByRole('heading', { level: 1, name: 'Audit Log' })).toBeInTheDocument()
        expect(screen.getByText('Activity Log')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /next/i }))
        expect(mockUseAuditLogs).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, per_page: 20 }))
    })
})
