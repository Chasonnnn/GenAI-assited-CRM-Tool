import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useMutation, useQueryClient } from '@tanstack/react-query'

vi.mock('@tanstack/react-query', async (importOriginal) => {
    const actual = await importOriginal<typeof import('@tanstack/react-query')>()
    return { ...actual, useMutation: vi.fn(), useQueryClient: vi.fn() }
})

import { useCreateInterviewNote, useDeleteInterviewNote } from '@/lib/hooks/use-interviews'

type MutationOptions = {
    onSuccess?: (data: unknown, variables: unknown) => void
}

describe('interview note mutations', () => {
    let capturedOptions: MutationOptions | null = null
    const invalidateQueries = vi.fn()

    beforeEach(() => {
        capturedOptions = null
        invalidateQueries.mockReset()
        vi.mocked(useQueryClient).mockReturnValue({
            invalidateQueries,
        } as unknown as ReturnType<typeof useQueryClient>)
        vi.mocked(useMutation).mockImplementation((options: unknown) => {
            capturedOptions = options as MutationOptions
            return { mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<
                typeof useMutation
            >
        })
    })

    function invalidatedKeys() {
        return invalidateQueries.mock.calls.map(([arg]) => (arg as { queryKey: unknown[] }).queryKey)
    }

    it('refreshes the interview list after adding a comment so notes_count updates', () => {
        useCreateInterviewNote()
        capturedOptions?.onSuccess?.({}, { interviewId: 'interview-1', data: {} })

        expect(invalidatedKeys()).toEqual(
            expect.arrayContaining([
                ['interviews', 'detail', 'interview-1', 'notes'],
                ['interviews', 'detail', 'interview-1'],
                ['interviews', 'list'],
            ]),
        )
    })

    it('refreshes the interview list after deleting a comment', () => {
        useDeleteInterviewNote()
        capturedOptions?.onSuccess?.({}, { interviewId: 'interview-1', noteId: 'note-1' })

        expect(invalidatedKeys()).toEqual(expect.arrayContaining([['interviews', 'list']]))
    })
})
