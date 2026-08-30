import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { useQuery } from '@tanstack/react-query'

vi.mock("@tanstack/react-query", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@tanstack/react-query")>()
    return { ...actual, useQuery: vi.fn() }
})

import WorkflowExecutionsPage from '../app/(app)/automation/executions/page'

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
    }),
    useSearchParams: () => ({
        get: vi.fn(() => null),
    }),
}))

vi.mock('next/link', () => ({
    default: ({
        href,
        children,
        prefetch: _prefetch,
        ...props
    }: {
        href: string | { pathname?: string }
        children: React.ReactNode
        prefetch?: boolean
    }) => (
        <a href={typeof href === 'string' ? href : href?.pathname ?? ''} {...props}>
            {children}
        </a>
    ),
}))

const mockExecution = {
    id: 'exec-1',
    status: 'partial',
    workflow_id: 'wf-1',
    workflow_name: 'Test Workflow',
    entity_type: 'surrogate',
    entity_id: 'sur-12345678',
    entity_name: 'Jane Applicant',
    entity_number: 'S12345',
    action_count: 2,
    duration_ms: 3200,
    executed_at: '2026-01-30T12:00:00Z',
    trigger_event: { source: 'test' },
    actions_executed: [
        { success: true, description: 'Created task: Follow up', duration_ms: 2500 },
        { success: false, action_type: 'send_email', error: 'Template missing', duration_ms: 800 },
    ],
    error_message: 'Workflow email bounced via Resend webhook',
}

describe('WorkflowExecutionsPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        ;(useQuery as ReturnType<typeof vi.fn>).mockImplementation(({ queryKey }) => {
            if (queryKey[0] === 'workflow-executions') {
                return { data: { items: [mockExecution], total: 1 }, isLoading: false, error: null }
            }
            if (queryKey[0] === 'workflow-execution-stats') {
                return {
                    data: { total_24h: 1, success_rate: 1, failed_24h: 0, avg_duration_ms: 1200 },
                    isLoading: false,
                    error: null,
                }
            }
            if (queryKey[0] === 'workflows-list') {
                return { data: [{ id: 'wf-1', name: 'Test Workflow' }], isLoading: false, error: null }
            }
            return { data: null, isLoading: false, error: null }
        })
    })

    it('renders action details from execution results', () => {
        render(<WorkflowExecutionsPage />)

        expect(screen.getByText('Test Workflow')).toBeInTheDocument()
        expect(screen.getByText('Jane Applicant (S12345)')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /expand row/i }))

        expect(screen.getByText('Actions Executed')).toBeInTheDocument()
        expect(screen.getByText('Created task: Follow up')).toBeInTheDocument()
        expect(screen.getByText('send_email')).toBeInTheDocument()
        expect(screen.getByText('Template missing')).toBeInTheDocument()
        expect(screen.getByText('2.5s')).toBeInTheDocument()
        expect(screen.getByText('800ms')).toBeInTheDocument()
        expect(screen.getByText(/workflow email bounced via resend webhook/i)).toBeInTheDocument()
    })

    it('routes donor executions through their donor subject context', () => {
        const donorExecution = {
            ...mockExecution,
            id: 'exec-donor-1',
            workflow_name: 'Egg donor follow-up',
            entity_type: 'task',
            entity_id: 'task-12345678',
            subject_type: 'egg_donor',
            subject_id: 'donor-12345678',
            entity_name: 'Maya Thompson',
            entity_number: 'D10001',
        }
        ;(useQuery as ReturnType<typeof vi.fn>).mockImplementation(({ queryKey }) => {
            if (queryKey[0] === 'workflow-executions') {
                return { data: { items: [donorExecution], total: 1 }, isLoading: false, error: null }
            }
            if (queryKey[0] === 'workflow-execution-stats') {
                return {
                    data: { total_24h: 1, success_rate: 1, failed_24h: 0, avg_duration_ms: 1200 },
                    isLoading: false,
                    error: null,
                }
            }
            if (queryKey[0] === 'workflows-list') {
                return { data: [], isLoading: false, error: null }
            }
            return { data: null, isLoading: false, error: null }
        })

        render(<WorkflowExecutionsPage />)

        expect(screen.getByRole('link', { name: 'D10001 — Maya Thompson' })).toHaveAttribute(
            'href',
            '/donors/donor-12345678',
        )
        expect(screen.queryByText(/donor-12345678/i)).not.toBeInTheDocument()
    })

    it('does not expose or link an unavailable donor identity', () => {
        const donorExecution = {
            ...mockExecution,
            id: 'exec-donor-unavailable',
            workflow_name: 'Egg donor follow-up',
            entity_type: 'task',
            entity_id: 'task-12345678',
            subject_type: 'egg_donor',
            subject_id: 'donor-secret-uuid',
            entity_name: null,
            entity_number: null,
        }
        ;(useQuery as ReturnType<typeof vi.fn>).mockImplementation(({ queryKey }) => {
            if (queryKey[0] === 'workflow-executions') {
                return { data: { items: [donorExecution], total: 1 }, isLoading: false, error: null }
            }
            if (queryKey[0] === 'workflow-execution-stats') {
                return {
                    data: { total_24h: 1, success_rate: 1, failed_24h: 0, avg_duration_ms: 1200 },
                    isLoading: false,
                    error: null,
                }
            }
            if (queryKey[0] === 'workflows-list') {
                return { data: [], isLoading: false, error: null }
            }
            return { data: null, isLoading: false, error: null }
        })

        render(<WorkflowExecutionsPage />)

        expect(screen.getByText('Donor unavailable')).toBeInTheDocument()
        expect(screen.queryByRole('link', { name: 'Donor unavailable' })).not.toBeInTheDocument()
        expect(screen.queryByText(/donor-secret/i)).not.toBeInTheDocument()
    })
})
