import type { ReactNode, ButtonHTMLAttributes } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { SurrogateInterviewTab } from '../components/surrogates/interviews/SurrogateInterviewTab'

const mockUseInterviews = vi.fn()
const mockUseInterview = vi.fn()
const mockUseInterviewNotes = vi.fn()
const mockUseInterviewAttachments = vi.fn()
const mockCreateInterview = vi.fn()
const mockUpdateInterview = vi.fn()
const mockDeleteInterview = vi.fn()
const mockCreateInterviewNote = vi.fn()
const mockDeleteInterviewNote = vi.fn()
const mockUploadInterviewAttachment = vi.fn()
const mockRequestTranscription = vi.fn()
const mockRefetchInterview = vi.fn()

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { role: 'case_manager', user_id: 'u1' } }),
}))

vi.mock('@/components/rich-text-editor', () => ({
    RichTextEditor: ({ onSubmit }: { onSubmit?: (value: string) => void }) => (
        <button type="button" onClick={() => onSubmit?.('<p>Note</p>')}>
            Add Note
        </button>
    ),
}))

vi.mock('@/components/surrogates/interviews/InterviewVersionHistory', () => ({
    InterviewVersionHistory: () => <div data-testid="interview-version-history" />,
}))

// Simplify Base UI dropdowns/dialogs to avoid portal/focus issues in tests.
vi.mock('@/components/ui/dropdown-menu', () => ({
    DropdownMenu: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DropdownMenuTrigger: ({
        children,
        ...props
    }: { children?: ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
    DropdownMenuContent: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DropdownMenuItem: ({
        children,
        onClick,
        onSelect,
        ...props
    }: {
        children?: ReactNode
        onClick?: () => void
        onSelect?: () => void
    }) => (
        <button
            type="button"
            onClick={() => {
                onClick?.()
                onSelect?.()
            }}
            {...props}
        >
            {children}
        </button>
    ),
}))

vi.mock('@/components/ui/dialog', () => ({
    Dialog: ({ open, children }: { open?: boolean; children?: ReactNode }) =>
        open ? <div>{children}</div> : null,
    DialogContent: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}))

vi.mock('@/lib/hooks/use-interviews', () => ({
    useInterviews: (surrogateId: string) => mockUseInterviews(surrogateId),
    useInterview: (interviewId: string) => mockUseInterview(interviewId),
    useInterviewNotes: (interviewId: string) => mockUseInterviewNotes(interviewId),
    useInterviewAttachments: (interviewId: string) => mockUseInterviewAttachments(interviewId),
    useCreateInterview: () => ({ mutateAsync: mockCreateInterview, isPending: false }),
    useUpdateInterview: () => ({ mutateAsync: mockUpdateInterview, isPending: false }),
    useDeleteInterview: () => ({ mutateAsync: mockDeleteInterview, isPending: false }),
    useCreateInterviewNote: () => ({ mutateAsync: mockCreateInterviewNote, isPending: false }),
    useUpdateInterviewNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteInterviewNote: () => ({ mutateAsync: mockDeleteInterviewNote, isPending: false }),
    useUploadInterviewAttachment: () => ({ mutateAsync: mockUploadInterviewAttachment, isPending: false }),
    useRequestTranscription: () => ({ mutateAsync: mockRequestTranscription, isPending: false }),
    useSummarizeInterview: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('SurrogateInterviewTab', () => {
    const now = new Date().toISOString()
    const interviewList = [
        {
            id: 'i1',
            interview_type: 'phone',
            conducted_at: now,
            conducted_by_user_id: 'u1',
            conducted_by_name: 'Alex Reviewer',
            duration_minutes: 25,
            status: 'completed',
            has_transcript: true,
            transcript_version: 2,
            notes_count: 1,
            attachments_count: 1,
            created_at: now,
        },
    ]
    const interviewDetail = {
        id: 'i1',
        surrogate_id: 'c1',
        interview_type: 'phone',
        conducted_at: now,
        conducted_by_user_id: 'u1',
        conducted_by_name: 'Alex Reviewer',
        duration_minutes: 25,
        transcript_json: {
            type: 'doc',
            content: [
                {
                    type: 'paragraph',
                    content: [{ type: 'text', text: 'Transcript' }],
                },
            ],
        },
        transcript_version: 2,
        transcript_size_bytes: 1200,
        is_transcript_offloaded: false,
        status: 'completed',
        notes_count: 1,
        attachments_count: 1,
        versions_count: 2,
        expires_at: null,
        created_at: now,
        updated_at: now,
    }
    const attachments = [
        {
            id: 'ia1',
            attachment_id: 'att1',
            filename: 'audio.mp3',
            content_type: 'audio/mpeg',
            file_size: 12000,
            is_audio_video: true,
            transcription_status: 'not_started',
            transcription_error: null,
            uploaded_by_name: 'Alex Reviewer',
            created_at: now,
        },
    ]

    beforeEach(() => {
        mockUseInterviews.mockReturnValue({ data: interviewList, isLoading: false })
        mockUseInterview.mockImplementation((interviewId: string) => ({
            data: interviewId ? interviewDetail : null,
            refetch: mockRefetchInterview,
        }))
        mockUseInterviewNotes.mockImplementation(() => ({ data: [] }))
        mockUseInterviewAttachments.mockImplementation((interviewId: string) => ({
            data: interviewId ? attachments : [],
        }))
        mockRequestTranscription.mockResolvedValue({})
    })

    it('renders empty state when no interviews exist', () => {
        mockUseInterviews.mockReturnValue({ data: [], isLoading: false })

        render(<SurrogateInterviewTab surrogateId="c1" />)

        expect(screen.getByText('No Interviews')).toBeDefined()
        expect(screen.getByRole('button', { name: /add interview/i })).toBeDefined()
    })

    it('requests transcription for audio attachments', async () => {
        render(<SurrogateInterviewTab surrogateId="c1" />)

        fireEvent.click(screen.getAllByText('Phone')[0])

        await waitFor(() => {
            expect(screen.getByText('Phone Interview')).toBeDefined()
        })

        fireEvent.click(screen.getByText('Attachments'))

        const transcribeButton = await screen.findByRole('button', { name: /transcribe/i })
        fireEvent.click(transcribeButton)

        await waitFor(() => {
            expect(mockRequestTranscription).toHaveBeenCalledWith({
                interviewId: 'i1',
                attachmentId: 'att1',
            })
        })
    })
})
