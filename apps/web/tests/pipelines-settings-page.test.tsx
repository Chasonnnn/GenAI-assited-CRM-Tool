import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import PipelinesSettingsPage from '../app/(app)/settings/pipelines/page'

const mockUseAuth = vi.fn()
const mockUsePipelines = vi.fn()
const mockUsePipeline = vi.fn()
const mockUsePipelineVersions = vi.fn()
const mockRollbackPipeline = vi.fn()
const mockUpdateStage = vi.fn()
const mockReorderStages = vi.fn()

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock('@/lib/hooks/use-pipelines', () => ({
    usePipelines: () => mockUsePipelines(),
    usePipeline: (id: string | null) => mockUsePipeline(id),
    usePipelineVersions: (id: string | null) => mockUsePipelineVersions(id),
    useRollbackPipeline: () => ({ mutateAsync: mockRollbackPipeline, isPending: false }),
    useUpdateStage: () => ({ mutateAsync: mockUpdateStage, isPending: false }),
    useReorderStages: () => ({ mutateAsync: mockReorderStages, isPending: false }),
}))

const pipelineFixture = {
    id: 'p1',
    name: 'Default Pipeline',
    is_default: true,
    stages: [
        {
            id: 's1',
            slug: 'new_unread',
            label: 'New Unread',
            color: '#3b82f6',
            order: 1,
            stage_type: 'intake',
            is_active: true,
        },
        {
            id: 's2',
            slug: 'contacted',
            label: 'Contacted',
            color: '#06b6d4',
            order: 2,
            stage_type: 'intake',
            is_active: true,
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
        mockRollbackPipeline.mockReset()
        mockUpdateStage.mockReset()
        mockReorderStages.mockReset()

        mockUseAuth.mockReturnValue({ user: { role: 'admin' } })
        mockUsePipelines.mockReturnValue({ data: [pipelineFixture], isLoading: false })
        mockUsePipeline.mockReturnValue({ data: pipelineFixture, isLoading: false })
        mockUsePipelineVersions.mockReturnValue({ data: [], isLoading: false, isError: false })
        mockUpdateStage.mockResolvedValue({})
        mockReorderStages.mockResolvedValue({})
    })

    it('renders stages with read-only slug inputs', () => {
        render(<PipelinesSettingsPage />)

        expect(screen.getByText('Pipeline Settings')).toBeInTheDocument()
        expect(screen.getByDisplayValue('New Unread')).toBeInTheDocument()

        // Slug inputs should be readonly
        const slugInput = screen.getByDisplayValue('new_unread')
        expect(slugInput).toBeDisabled()
        expect(slugInput).toHaveAttribute('readonly')
    })

    it('saves edited stage label using updateStage', async () => {
        render(<PipelinesSettingsPage />)

        const labelInputs = screen.getAllByPlaceholderText('Label')
        fireEvent.change(labelInputs[0], { target: { value: 'New Lead' } })

        expect(screen.getByText('Unsaved changes')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

        await waitFor(() => {
            expect(mockUpdateStage).toHaveBeenCalled()
        })

        const call = mockUpdateStage.mock.calls[0][0]
        expect(call.pipelineId).toBe('p1')
        expect(call.stageId).toBe('s1')
        expect(call.data.label).toBe('New Lead')
    })

    it('reorders stages and saves using reorderStages', async () => {
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
            expect(mockReorderStages).toHaveBeenCalled()
        })

        const call = mockReorderStages.mock.calls[0][0]
        expect(call.pipelineId).toBe('p1')
        // After drag: s2 is now first, s1 is second
        expect(call.orderedStageIds).toEqual(['s2', 's1'])
    })

    it('updates stage color and saves', async () => {
        render(<PipelinesSettingsPage />)

        const colorInputs = Array.from(document.querySelectorAll('input[type="color"]'))
        expect(colorInputs.length).toBeGreaterThan(0)

        fireEvent.change(colorInputs[0], { target: { value: '#ff0000' } })

        expect(screen.getByText('Unsaved changes')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

        await waitFor(() => {
            expect(mockUpdateStage).toHaveBeenCalled()
        })

        const call = mockUpdateStage.mock.calls[0][0]
        expect(call.data.color).toBe('#ff0000')
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
