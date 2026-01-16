import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SurrogateDetailPage from '../app/(app)/surrogates/[id]/page'

const mockPush = vi.fn()
const mockCreateZoomMeeting = vi.fn()
const mockSendZoomInvite = vi.fn()

vi.mock('next/navigation', () => ({
    useParams: () => ({ id: 'c1' }),
    useRouter: () => ({ push: mockPush }),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { role: 'developer' } }),
}))

vi.mock('@/components/rich-text-editor', () => ({
    RichTextEditor: () => <div data-testid="rich-text-editor" />,
}))

vi.mock('@/lib/hooks/use-user-integrations', () => ({
    useZoomStatus: () => ({ data: { connected: false, account_email: null } }),
    useCreateZoomMeeting: () => ({ mutateAsync: mockCreateZoomMeeting, isPending: false }),
    useSendZoomInvite: () => ({ mutateAsync: mockSendZoomInvite, isPending: false }),
}))

const mockUseQueues = vi.fn()
const mockClaimSurrogate = vi.fn()
const mockReleaseSurrogate = vi.fn()

vi.mock('@/lib/hooks/use-queues', () => ({
    useQueues: () => mockUseQueues(),
    useClaimSurrogate: () => ({ mutateAsync: mockClaimSurrogate, isPending: false }),
    useReleaseSurrogate: () => ({ mutateAsync: mockReleaseSurrogate, isPending: false }),
}))

const mockUseSurrogate = vi.fn()
const mockUseSurrogateActivity = vi.fn()
const mockUseSurrogateHistory = vi.fn()
const mockUseNotes = vi.fn()
const mockUseTasks = vi.fn()
const mockUseAttachments = vi.fn()

const mockChangeStatus = vi.fn()
const mockArchive = vi.fn()
const mockRestore = vi.fn()
const mockUpdateSurrogate = vi.fn()
const mockAssignSurrogate = vi.fn()
const mockUseAssignees = vi.fn()
const mockCreateNote = vi.fn()
const mockDeleteNote = vi.fn()
const mockCompleteTask = vi.fn()
const mockUncompleteTask = vi.fn()
const mockUpdateTask = vi.fn()
const mockCreateTask = vi.fn()
const mockDeleteTask = vi.fn()

const baseSurrogateData = {
    id: 'c1',
    surrogate_number: 'S12345',
    full_name: 'Jane Applicant',
    status_label: 'New Unread',
    stage_id: 's1',
    stage_slug: 'new_unread',
    stage_type: 'intake',
    source: 'manual',
    email: 'jane@example.com',
    phone: null,
    state: null,
    is_priority: false,
    is_archived: false,
    owner_type: 'user',
    owner_id: 'u1',
    owner_name: null,
    age: null,
    bmi: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    created_by_user_id: null,
    date_of_birth: null,
    race: null,
    height_ft: null,
    weight_lb: null,
    is_age_eligible: null,
    is_citizen_or_pr: null,
    has_child: null,
    is_non_smoker: null,
    has_surrogate_experience: null,
    num_deliveries: null,
    num_csections: null,
    archived_at: null,
    // Insurance info
    insurance_company: null,
    insurance_plan_name: null,
    insurance_phone: null,
    insurance_policy_number: null,
    insurance_member_id: null,
    insurance_group_number: null,
    insurance_subscriber_name: null,
    insurance_subscriber_dob: null,
    // IVF clinic
    clinic_name: null,
    clinic_address_line1: null,
    clinic_address_line2: null,
    clinic_city: null,
    clinic_state: null,
    clinic_postal: null,
    clinic_phone: null,
    clinic_email: null,
    // Monitoring clinic
    monitoring_clinic_name: null,
    monitoring_clinic_address_line1: null,
    monitoring_clinic_address_line2: null,
    monitoring_clinic_city: null,
    monitoring_clinic_state: null,
    monitoring_clinic_postal: null,
    monitoring_clinic_phone: null,
    monitoring_clinic_email: null,
    // OB provider
    ob_provider_name: null,
    ob_clinic_name: null,
    ob_address_line1: null,
    ob_address_line2: null,
    ob_city: null,
    ob_state: null,
    ob_postal: null,
    ob_phone: null,
    ob_email: null,
    // Delivery hospital
    delivery_hospital_name: null,
    delivery_hospital_address_line1: null,
    delivery_hospital_address_line2: null,
    delivery_hospital_city: null,
    delivery_hospital_state: null,
    delivery_hospital_postal: null,
    delivery_hospital_phone: null,
    delivery_hospital_email: null,
    // Pregnancy tracking
    pregnancy_start_date: null,
    pregnancy_due_date: null,
}

vi.mock('@/lib/hooks/use-surrogates', () => ({
    useSurrogate: (id: string) => mockUseSurrogate(id),
    useSurrogateActivity: (id: string) => mockUseSurrogateActivity(id),
    useSurrogateHistory: (id: string) => mockUseSurrogateHistory(id),
    useChangeSurrogateStatus: () => ({ mutateAsync: mockChangeStatus }),
    useArchiveSurrogate: () => ({ mutateAsync: mockArchive }),
    useRestoreSurrogate: () => ({ mutateAsync: mockRestore }),
    useUpdateSurrogate: () => ({ mutateAsync: mockUpdateSurrogate }),
    useAssignSurrogate: () => ({ mutateAsync: mockAssignSurrogate }),
    useAssignees: () => mockUseAssignees(),
    useSendSurrogateEmail: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCreateContactAttempt: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useContactAttempts: () => ({ data: null, isLoading: false }),
}))

vi.mock('@/lib/hooks/use-notes', () => ({
    useNotes: (surrogateId: string) => mockUseNotes(surrogateId),
    useCreateNote: () => ({ mutateAsync: mockCreateNote }),
    useDeleteNote: () => ({ mutateAsync: mockDeleteNote }),
}))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (params: unknown) => mockUseTasks(params),
    useCompleteTask: () => ({ mutateAsync: mockCompleteTask }),
    useUncompleteTask: () => ({ mutateAsync: mockUncompleteTask }),
    useUpdateTask: () => ({ mutateAsync: mockUpdateTask }),
    useCreateTask: () => ({ mutateAsync: mockCreateTask, isPending: false }),
    useDeleteTask: () => ({ mutateAsync: mockDeleteTask, isPending: false }),
}))

vi.mock('@/lib/hooks/use-attachments', () => ({
    useAttachments: (surrogateId: string | null) => mockUseAttachments(surrogateId),
}))

vi.mock('@/lib/hooks/use-ai', () => ({
    useSummarizeSurrogate: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDraftEmail: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useAISettings: () => ({ data: { is_enabled: false } }),
}))

vi.mock('@/lib/hooks/use-pipelines', () => ({
    useDefaultPipeline: () => ({
        data: {
            id: 'p1',
            stages: [
                { id: 's1', slug: 'new_unread', label: 'New Unread', color: '#3b82f6', stage_type: 'intake', order: 1, is_active: true },
                { id: 's2', slug: 'ready_to_match', label: 'Ready to Match', color: '#10b981', stage_type: 'post_approval', order: 10, is_active: true },
                { id: 's3', slug: 'heartbeat_confirmed', label: 'Heartbeat Confirmed', color: '#f97316', stage_type: 'post_approval', order: 20, is_active: true },
            ],
        },
        isLoading: false,
    }),
}))

vi.mock('@/lib/hooks/use-email-templates', () => ({
    useEmailTemplates: () => ({ data: [], isLoading: false }),
    useEmailTemplate: () => ({ data: null, isLoading: false }),  // singular for detail
    useSendEmail: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/hooks/use-intended-parents', () => ({
    useIntendedParents: () => ({ data: { items: [] }, isLoading: false }),
}))

vi.mock('@/lib/hooks/use-matches', () => ({
    useCreateMatch: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('SurrogateDetailPage', () => {
    beforeEach(() => {
        mockUseAssignees.mockReturnValue({ data: [] })
        mockUseSurrogate.mockReturnValue({
            data: {
                ...baseSurrogateData,
            },
            isLoading: false,
            error: null,
        })

        mockUseSurrogateActivity.mockReturnValue({ data: { items: [] } })
        mockUseSurrogateHistory.mockReturnValue({ data: [] })
        mockUseNotes.mockReturnValue({ data: [] })
        mockUseTasks.mockReturnValue({ data: { items: [] } })
        mockUseQueues.mockReturnValue({ data: [] })
        mockUseAttachments.mockReturnValue({ data: [] })

        mockPush.mockReset()
        mockClaimSurrogate.mockReset()
        mockReleaseSurrogate.mockReset()
        const clipboardWriteText = navigator.clipboard.writeText as unknown as { mockClear?: () => void }
        clipboardWriteText.mockClear?.()
    })

    it('renders surrogate header and allows copying email', () => {
        render(<SurrogateDetailPage />)

        expect(screen.getByText('Surrogate #S12345')).toBeInTheDocument()
        expect(screen.getByText('Jane Applicant')).toBeInTheDocument()
        expect(screen.getByText('jane@example.com')).toBeInTheDocument()

        const emailRow = screen.getByText('Email:').parentElement
        const copyButton = emailRow?.querySelector('button')
        expect(copyButton).toBeTruthy()

        fireEvent.click(copyButton!)
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('jane@example.com')
    })

    it('shows Claim Surrogate for queue-owned surrogates', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                owner_type: 'queue',
                owner_id: 'q1',
            },
            isLoading: false,
            error: null,
        })

        render(<SurrogateDetailPage />)

        fireEvent.click(screen.getByRole('button', { name: 'Claim Surrogate' }))
        expect(mockClaimSurrogate).toHaveBeenCalledWith('c1')
    })

    it('shows Insurance Info and Latest Updates on overview', () => {
        mockUseNotes.mockReturnValue({
            data: [
                {
                    id: 'n1',
                    surrogate_id: 'c1',
                    author_name: 'Case Manager',
                    body: '<p>Latest note content</p>',
                    created_at: new Date().toISOString(),
                },
            ],
        })
        mockUseAttachments.mockReturnValue({
            data: [
                {
                    id: 'a1',
                    filename: 'intake.pdf',
                    content_type: 'application/pdf',
                    file_size: 12345,
                    scan_status: 'clean',
                    quarantined: false,
                    uploaded_by_user_id: null,
                    created_at: new Date().toISOString(),
                },
            ],
        })
        mockUseSurrogateHistory.mockReturnValue({
            data: [
                {
                    id: 'h1',
                    from_stage_id: 's1',
                    to_stage_id: 's2',
                    from_label_snapshot: 'New Unread',
                    to_label_snapshot: 'Ready to Match',
                    changed_by_user_id: 'u1',
                    changed_by_name: 'Case Manager',
                    reason: null,
                    changed_at: new Date().toISOString(),
                },
            ],
        })

        render(<SurrogateDetailPage />)

        expect(screen.getByText('Insurance Information')).toBeInTheDocument()
        expect(screen.getByText('Latest Updates')).toBeInTheDocument()
        expect(screen.getByText('Latest note content')).toBeInTheDocument()
        expect(screen.getByText('intake.pdf')).toBeInTheDocument()
    })

    it('hides Medical Information and Pregnancy Tracker before ready_to_match', () => {
        render(<SurrogateDetailPage />)

        expect(screen.queryByText('Medical Information')).not.toBeInTheDocument()
        expect(screen.queryByText('Pregnancy Tracker')).not.toBeInTheDocument()
    })

    it('shows Medical Information and Pregnancy Tracker at heartbeat_confirmed', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                status_label: 'Heartbeat Confirmed',
                stage_id: 's3',
                stage_slug: 'heartbeat_confirmed',
                stage_type: 'post_approval',
            },
            isLoading: false,
            error: null,
        })

        render(<SurrogateDetailPage />)

        expect(screen.getByText('Medical Information')).toBeInTheDocument()
        expect(screen.getByText('Pregnancy Tracker')).toBeInTheDocument()
        expect(screen.queryByText('Due Date:')).not.toBeInTheDocument()
    })

    it('shows Due Date row when pregnancy start date is set', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                status_label: 'Heartbeat Confirmed',
                stage_id: 's3',
                stage_slug: 'heartbeat_confirmed',
                stage_type: 'post_approval',
                pregnancy_start_date: '2025-01-10',
                pregnancy_due_date: null,
            },
            isLoading: false,
            error: null,
        })

        render(<SurrogateDetailPage />)

        expect(screen.getByText('Pregnancy Tracker')).toBeInTheDocument()
        expect(screen.getByText('Due Date:')).toBeInTheDocument()
    })
})
