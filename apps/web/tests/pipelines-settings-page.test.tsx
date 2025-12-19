import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import PipelinesSettingsPage from '../app/(app)/settings/pipelines/page'

const mockUseAuth = vi.fn()
const mockUsePipelines = vi.fn()
const mockUsePipeline = vi.fn()
const mockUsePipelineVersions = vi.fn()
const mockUpdatePipeline = vi.fn()
const mockRollbackPipeline = vi.fn()

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock('@/lib/hooks/use-pipelines', () => ({
    usePipelines: () => mockUsePipelines(),
    usePipeline: (id: string | null) => mockUsePipeline(id),
    usePipelineVersions: (id: string | null) => mockUsePipelineVersions(id),
    useUpdatePipeline: () => ({ mutateAsync: mockUpdatePipeline, isPending: false }),
    useRollbackPipeline: () => ({ mutateAsync: mockRollbackPipeline, isPending: false }),
}))

const pipelineFixture = {
    id: 'p1',
    name: 'Default Pipeline',
    is_default: true,
    stages: [
        {
            status: 'new_unread',
            label: 'New Unread',
            color: '#3b82f6',
            order: 1,
            visible: true,
        },
        {
            status: 'contacted',
            label: 'Contacted',
            color: '#06b6d4',
            order: 2,
            visible: true,
        },
    ],
    current_version: 2,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
}

describe('PipelinesSettingsPage', () => {
    beforeEach(() => {
        mockUseAuth.mockReset()
        mockUsePipelines.mockReset()
        mockUsePipeline.mockReset()
        mockUsePipelineVersions.mockReset()
        mockUpdatePipeline.mockReset()
        mockRollbackPipeline.mockReset()

        mockUseAuth.mockReturnValue({ user: { role: 'manager' } })
        mockUsePipelines.mockReturnValue({ data: [pipelineFixture], isLoading: false })
        mockUsePipeline.mockReturnValue({ data: pipelineFixture, isLoading: false })
        mockUsePipelineVersions.mockReturnValue({ data: [], isLoading: false, isError: false })
        mockUpdatePipeline.mockResolvedValue(pipelineFixture)
    })

    it('renders stages with read-only status keys', () => {
        render(<PipelinesSettingsPage />)

        expect(screen.getByText('Pipeline Settings')).toBeInTheDocument()
        expect(screen.getByDisplayValue('New Unread')).toBeInTheDocument()

        const statusInput = screen.getByDisplayValue('new_unread')
        expect(statusInput).toBeDisabled()
        expect(statusInput).toHaveAttribute('readonly')
    })

    it('saves edited stages with expected version', async () => {
        render(<PipelinesSettingsPage />)

        const labelInputs = screen.getAllByPlaceholderText('Label')
        fireEvent.change(labelInputs[0], { target: { value: 'New Lead' } })

        expect(screen.getByText('Unsaved changes')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

        await waitFor(() => {
            expect(mockUpdatePipeline).toHaveBeenCalled()
        })

        const call = mockUpdatePipeline.mock.calls[0][0]
        expect(call.id).toBe('p1')
        expect(call.data.expected_version).toBe(2)
        expect(call.data.stages[0].label).toBe('New Lead')
    })

    it('reorders stages and saves updated order', async () => {
        render(<PipelinesSettingsPage />)

        const firstRow = screen.getByDisplayValue('New Unread').closest('[draggable="true"]')
        const secondRow = screen.getByDisplayValue('Contacted').closest('[draggable="true"]')

        expect(firstRow).toBeTruthy()
        expect(secondRow).toBeTruthy()

        fireEvent.dragStart(firstRow as HTMLElement)
        fireEvent.dragOver(secondRow as HTMLElement)
        fireEvent.dragEnd(firstRow as HTMLElement)

        expect(screen.getByText('Unsaved changes')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

        await waitFor(() => {
            expect(mockUpdatePipeline).toHaveBeenCalled()
        })

        const call = mockUpdatePipeline.mock.calls[0][0]
        expect(call.data.stages[0].status).toBe('contacted')
        expect(call.data.stages[0].order).toBe(1)
        expect(call.data.stages[1].status).toBe('new_unread')
        expect(call.data.stages[1].order).toBe(2)
    })

    it('updates stage color and saves', async () => {
        render(<PipelinesSettingsPage />)

        const colorInputs = Array.from(document.querySelectorAll('input[type="color"]'))
        expect(colorInputs.length).toBeGreaterThan(0)

        fireEvent.change(colorInputs[0], { target: { value: '#ff0000' } })

        expect(screen.getByText('Unsaved changes')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

        await waitFor(() => {
            expect(mockUpdatePipeline).toHaveBeenCalled()
        })

        const call = mockUpdatePipeline.mock.calls[0][0]
        expect(call.data.stages[0].color).toBe('#ff0000')
    })

    it('saves change note comment with the update', async () => {
        render(<PipelinesSettingsPage />)

        const labelInputs = screen.getAllByPlaceholderText('Label')
        fireEvent.change(labelInputs[0], { target: { value: 'New Lead' } })

        const commentInput = screen.getByLabelText('Change Note (optional)')
        fireEvent.change(commentInput, { target: { value: 'Renamed first stage' } })

        fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

        await waitFor(() => {
            expect(mockUpdatePipeline).toHaveBeenCalled()
        })

        const call = mockUpdatePipeline.mock.calls[0][0]
        expect(call.data.comment).toBe('Renamed first stage')
    })

    it('rolls back to a previous version', async () => {
        mockUseAuth.mockReturnValue({ user: { role: 'developer' } })
        mockUsePipelineVersions.mockReturnValue({
            data: [
                {
                    id: 'v2',
                    version: 2,
                    created_at: new Date().toISOString(),
                    comment: 'Current'
                },
                {
                    id: 'v1',
                    version: 1,
                    created_at: new Date(Date.now() - 86400000).toISOString(),
                    comment: 'Initial'
                }
            ],
            isLoading: false,
            isError: false
        })
        mockRollbackPipeline.mockResolvedValue({})

        render(<PipelinesSettingsPage />)

        fireEvent.click(screen.getByRole('button', { name: /restore/i }))

        await waitFor(() => {
            expect(mockRollbackPipeline).toHaveBeenCalledWith({ id: 'p1', version: 1 })
        })
    })

    it('shows version history access message for non-developers on error', () => {
        mockUsePipelineVersions.mockReturnValue({ data: [], isLoading: false, isError: true })

        render(<PipelinesSettingsPage />)

        expect(screen.getByText('Version history requires Developer role')).toBeInTheDocument()
    })
})
