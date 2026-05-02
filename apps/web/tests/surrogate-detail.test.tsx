import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { SurrogateDetailLayoutClient } from '@/components/surrogates/detail/SurrogateDetailLayoutClient'
import { SurrogateOverviewTab } from '@/components/surrogates/detail/tabs/SurrogateOverviewTab'
import { SurrogateDetailHeader } from '@/components/surrogates/detail/SurrogateDetailHeader'
import SurrogateJourneyPage from '../app/(app)/surrogates/[id]/journey/page'

const mockPush = vi.fn()
const mockReplace = vi.fn()
const mockParams = {
    id: 'c1',
}
const mockSegment = { value: null as string | null }
const mockDetailSearchParams = new URLSearchParams()
const mockCreateZoomMeeting = vi.fn()
const mockSendZoomInvite = vi.fn()

vi.mock('next/navigation', () => ({
    useParams: () => mockParams,
    useRouter: () => ({ push: mockPush, replace: mockReplace }),
    useSelectedLayoutSegment: () => mockSegment.value,
    useSearchParams: () => ({
        get: (key: string) => mockDetailSearchParams.get(key),
        toString: () => mockDetailSearchParams.toString(),
    }),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => ({ user: { role: 'developer' } }),
}))

vi.mock('@/components/rich-text-editor', () => ({
    RichTextEditor: () => <div data-testid="rich-text-editor" />,
}))

vi.mock('@/components/surrogates/journey/SurrogateJourneyTab', () => ({
    SurrogateJourneyTab: ({ surrogateId }: { surrogateId: string }) => (
        <div>Journey timeline for {surrogateId}</div>
    ),
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
const mockRevealSurrogateSensitiveInfo = vi.fn()
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
    stage_key: 'new_unread',
    stage_slug: 'new_unread',
    stage_type: 'intake',
    paused_from_stage_id: null,
    paused_from_stage_key: null,
    paused_from_stage_slug: null,
    paused_from_stage_label: null,
    paused_from_stage_type: null,
    source: 'manual',
    email: 'jane@example.com',
    phone: null,
    state: null,
    is_priority: false,
    is_archived: false,
    sensitive_info_available: false,
    marital_status: null,
    ssn_masked: null,
    partner_name: null,
    partner_email: null,
    partner_phone: null,
    partner_ssn_masked: null,
    partner_address_line1: null,
    partner_address_line2: null,
    partner_city: null,
    partner_state: null,
    partner_postal: null,
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
    journey_timing_preference: null,
    num_deliveries: null,
    num_csections: null,
    eligibility_checklist: [],
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
    insurance_fax: null,
    // IVF clinic
    clinic_name: null,
    clinic_address_line1: null,
    clinic_address_line2: null,
    clinic_city: null,
    clinic_state: null,
    clinic_postal: null,
    clinic_phone: null,
    clinic_fax: null,
    clinic_email: null,
    // Monitoring clinic
    monitoring_clinic_name: null,
    monitoring_clinic_address_line1: null,
    monitoring_clinic_address_line2: null,
    monitoring_clinic_city: null,
    monitoring_clinic_state: null,
    monitoring_clinic_postal: null,
    monitoring_clinic_phone: null,
    monitoring_clinic_fax: null,
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
    ob_fax: null,
    ob_email: null,
    // PCP
    pcp_provider_name: null,
    pcp_name: null,
    pcp_address_line1: null,
    pcp_address_line2: null,
    pcp_city: null,
    pcp_state: null,
    pcp_postal: null,
    pcp_phone: null,
    pcp_fax: null,
    pcp_email: null,
    // Lab clinic
    lab_clinic_name: null,
    lab_clinic_address_line1: null,
    lab_clinic_address_line2: null,
    lab_clinic_city: null,
    lab_clinic_state: null,
    lab_clinic_postal: null,
    lab_clinic_phone: null,
    lab_clinic_fax: null,
    lab_clinic_email: null,
    // Delivery hospital
    delivery_hospital_name: null,
    delivery_hospital_address_line1: null,
    delivery_hospital_address_line2: null,
    delivery_hospital_city: null,
    delivery_hospital_state: null,
    delivery_hospital_postal: null,
    delivery_hospital_phone: null,
    delivery_hospital_fax: null,
    delivery_hospital_email: null,
    // Pregnancy tracking
    pregnancy_start_date: null,
    pregnancy_due_date: null,
    actual_delivery_date: null,
    delivery_baby_gender: null,
    delivery_baby_weight: null,
    latest_contact_outcome: null,
    latest_interview_outcome: null,
}

const defaultPipelineStages = [
    { id: 's1', stage_key: 'new_unread', slug: 'new_unread', label: 'New Unread', color: '#3b82f6', stage_type: 'intake', order: 1, is_active: true },
    { id: 's1b', stage_key: 'pending_docusign', slug: 'pending_docusign', label: 'Pending-DocuSign', color: '#f59e0b', stage_type: 'intake', order: 6, is_active: true },
    { id: 's2', stage_key: 'ready_to_match', slug: 'ready_to_match', label: 'Ready to Match', color: '#10b981', stage_type: 'post_approval', order: 10, is_active: true },
    { id: 's2b', stage_key: 'matched', slug: 'matched', label: 'Matched', color: '#6366f1', stage_type: 'post_approval', order: 15, is_active: true },
    { id: 's3', stage_key: 'heartbeat_confirmed', slug: 'heartbeat_confirmed', label: 'Heartbeat Confirmed', color: '#f97316', stage_type: 'post_approval', order: 20, is_active: true },
    { id: 's4', stage_key: 'on_hold', slug: 'on_hold', label: 'On-Hold', color: '#b4536a', stage_type: 'paused', order: 89, is_active: true },
    { id: 's5', stage_key: 'lost', slug: 'lost', label: 'Lost', color: '#ef4444', stage_type: 'terminal', order: 90, is_active: true },
    { id: 's6', stage_key: 'disqualified', slug: 'disqualified', label: 'Disqualified', color: '#dc2626', stage_type: 'terminal', order: 91, is_active: true },
]
let mockPipelineStages = [...defaultPipelineStages]

vi.mock('@/lib/hooks/use-surrogates', () => ({
    useSurrogate: (id: string) => mockUseSurrogate(id),
    useSurrogateActivity: (id: string) => mockUseSurrogateActivity(id),
    useSurrogateHistory: (id: string) => mockUseSurrogateHistory(id),
    useSurrogateTemplateVariables: () => ({ data: {}, isLoading: false }),
    useChangeSurrogateStatus: () => ({ mutateAsync: mockChangeStatus }),
    useArchiveSurrogate: () => ({ mutateAsync: mockArchive }),
    useRestoreSurrogate: () => ({ mutateAsync: mockRestore }),
    useUpdateSurrogate: () => ({ mutateAsync: mockUpdateSurrogate }),
    useRevealSurrogateSensitiveInfo: () => ({ mutateAsync: mockRevealSurrogateSensitiveInfo, isPending: false }),
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
    useUploadAttachment: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDownloadAttachment: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteAttachment: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useAttachmentDownloadUrl: () => ({ mutateAsync: async () => ({ download_url: "" }), isPending: false }),
    useImageAttachments: () => ({ data: [], isLoading: false }),
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
            stages: mockPipelineStages,
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
        mockPipelineStages = [...defaultPipelineStages]
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
        mockReplace.mockReset()
        mockSegment.value = null
        mockDetailSearchParams.delete('return_to')
        mockChangeStatus.mockReset()
        mockClaimSurrogate.mockReset()
        mockReleaseSurrogate.mockReset()
        mockUpdateSurrogate.mockReset()
        mockRevealSurrogateSensitiveInfo.mockReset()
        const clipboardWriteText = navigator.clipboard.writeText as unknown as { mockClear?: () => void }
        clipboardWriteText.mockClear?.()
    })

    it('renders surrogate header and allows copying email', () => {
        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('Surrogate #S12345')).toBeInTheDocument()
        expect(screen.getByText('Jane Applicant')).toBeInTheDocument()
        expect(screen.getByText('jane@example.com')).toBeInTheDocument()

        const emailRow = screen.getByText('Email:').parentElement
        const copyButton = emailRow?.querySelector('button')
        expect(copyButton).toBeTruthy()

        fireEvent.click(copyButton!)
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith('jane@example.com')
    })

    it('hides personal information before Pending-DocuSign', () => {
        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.queryByText('Personal Information')).not.toBeInTheDocument()
        expect(screen.queryByText('Marital Status:')).not.toBeInTheDocument()
    })

    it('shows masked personal information and reveals SSN at Pending-DocuSign', async () => {
        mockRevealSurrogateSensitiveInfo.mockResolvedValueOnce({
            ssn: '123-45-6789',
            partner_ssn: '987-65-4321',
        })
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                status_label: 'Pending-DocuSign',
                stage_id: 's1b',
                stage_key: 'pending_docusign',
                stage_slug: 'pending_docusign',
                sensitive_info_available: true,
                marital_status: 'Married',
                ssn_masked: '***-**-6789',
                partner_name: 'Taylor Partner',
                partner_email: 'partner@example.com',
                partner_phone: '+15551234567',
                partner_ssn_masked: '***-**-4321',
                partner_address_line1: '123 Partner St',
                partner_address_line2: 'Apt 4',
                partner_city: 'Austin',
                partner_state: 'TX',
                partner_postal: '78701',
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('Personal Information')).toBeInTheDocument()
        expect(screen.getByText('Married')).toBeInTheDocument()
        expect(screen.getByText('***-**-6789')).toBeInTheDocument()
        expect(screen.getByText('Taylor Partner')).toBeInTheDocument()
        expect(screen.getByText('***-**-4321')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: 'Reveal surrogate SSN' }))

        await waitFor(() => {
            expect(mockRevealSurrogateSensitiveInfo).toHaveBeenCalledWith('c1')
        })
        expect(await screen.findByText('123-45-6789')).toBeInTheDocument()
        expect(screen.getByText('987-65-4321')).toBeInTheDocument()
    })

    it('updates personal information fields from the overview section', async () => {
        mockUpdateSurrogate.mockResolvedValue({
            ...baseSurrogateData,
            partner_name: 'Jordan Partner',
        })
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                status_label: 'Pending-DocuSign',
                stage_id: 's1b',
                stage_key: 'pending_docusign',
                stage_slug: 'pending_docusign',
                sensitive_info_available: true,
                partner_name: 'Taylor Partner',
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        fireEvent.click(screen.getByRole('button', { name: 'Edit Partner name' }))
        const input = screen.getByLabelText('Partner name')
        fireEvent.change(input, { target: { value: 'Jordan Partner' } })
        fireEvent.keyDown(input, { key: 'Enter' })

        await waitFor(() => {
            expect(mockUpdateSurrogate).toHaveBeenCalledWith({
                surrogateId: 'c1',
                data: { partner_name: 'Jordan Partner' },
            })
        })
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

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        fireEvent.click(screen.getByRole('button', { name: 'Claim Surrogate' }))
        expect(mockClaimSurrogate).toHaveBeenCalledWith('c1')
    })

    it('selects tab from url params', () => {
        mockSegment.value = 'history'

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        const historyTab = screen.getByRole('tab', { name: /History/i })
        expect(historyTab).toHaveAttribute('aria-selected', 'true')
    })

    it('updates url when switching tabs', () => {
        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        fireEvent.click(screen.getByRole('tab', { name: /Notes/i }))
        expect(mockReplace).toHaveBeenCalledWith('/surrogates/c1/notes', { scroll: false })
    })

    it('keeps Journey tab enabled before matched and hides global helper text', () => {
        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        const journeyTab = screen.getByRole('tab', { name: /Journey/i })
        expect(journeyTab).not.toHaveAttribute('aria-disabled', 'true')
        expect(screen.queryByText('Journey available after Match Confirmed')).not.toBeInTheDocument()
    })

    it('does not redirect when journey tab is requested before matched', () => {
        mockSegment.value = 'journey'

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(mockReplace).not.toHaveBeenCalledWith('/surrogates/c1', { scroll: false })
    })

    it('shows journey empty state before match confirmation', () => {
        mockSegment.value = 'journey'

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateJourneyPage />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('No journey available yet')).toBeInTheDocument()
        expect(screen.getByText('Journey becomes available after Match Confirmed.')).toBeInTheDocument()
    })

    it('shows Insurance Info and Activity on overview', () => {
        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('Medical & Insurance')).toBeInTheDocument()
        expect(screen.getByText('Activity')).toBeInTheDocument()
    })

    it("renders surrogate header and triggers back", () => {
        const onBack = vi.fn()

        render(
            <SurrogateDetailHeader
                surrogateNumber="S12345"
                statusLabel="New Unread"
                statusColor="#111111"
                isArchived={false}
                onBack={onBack}
            >
                <div>Actions</div>
            </SurrogateDetailHeader>
        )

        expect(screen.getByText("Surrogate #S12345")).toBeInTheDocument()
        expect(screen.getByText("New Unread")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Back" }))
        expect(onBack).toHaveBeenCalled()
    })

    it("shows only the contact outcome pill at the contacted stage", () => {
        render(
            <SurrogateDetailHeader
                surrogateNumber="S12345"
                currentStageKey="contacted"
                statusLabel="Contacted"
                statusColor="#111111"
                latestContactOutcome={{ outcome: "reached", at: "2024-02-01T10:00:00Z" }}
                latestInterviewOutcome={{ outcome: "no_show", at: "2024-02-01T12:00:00Z" }}
                isArchived={false}
                onBack={vi.fn()}
            />
        )

        expect(screen.getByText("Contact: Reached")).toBeInTheDocument()
        expect(screen.queryByText("Interview: No Show")).not.toBeInTheDocument()
        expect(screen.getByText("Contacted")).toHaveStyle({ backgroundColor: "#111111" })
    })

    it("shows only the interview outcome pill at the interview scheduled stage", () => {
        render(
            <SurrogateDetailHeader
                surrogateNumber="S12345"
                currentStageKey="interview_scheduled"
                statusLabel="Interview Scheduled"
                statusColor="#222222"
                latestContactOutcome={{ outcome: "reached", at: "2024-02-01T10:00:00Z" }}
                latestInterviewOutcome={{ outcome: "no_show", at: "2024-02-01T12:00:00Z" }}
                isArchived={false}
                onBack={vi.fn()}
            />
        )

        expect(screen.queryByText("Contact: Reached")).not.toBeInTheDocument()
        expect(screen.getByText("Interview: No Show")).toBeInTheDocument()
    })

    it("hides outcome pills after the surrogate moves past the corresponding stages", () => {
        render(
            <SurrogateDetailHeader
                surrogateNumber="S12345"
                currentStageKey="under_review"
                statusLabel="Under Review"
                statusColor="#333333"
                latestContactOutcome={{ outcome: "reached", at: "2024-02-01T10:00:00Z" }}
                latestInterviewOutcome={{ outcome: "no_show", at: "2024-02-01T12:00:00Z" }}
                isArchived={false}
                onBack={vi.fn()}
            />
        )

        expect(screen.queryByText("Contact: Reached")).not.toBeInTheDocument()
        expect(screen.queryByText("Interview: No Show")).not.toBeInTheDocument()
    })

    it('returns to the filtered surrogates list when return_to is present', () => {
        mockDetailSearchParams.set('return_to', '/surrogates?stage=s1&q=john&page=2')

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        fireEvent.click(screen.getByRole('button', { name: 'Back' }))

        expect(mockPush).toHaveBeenCalledWith('/surrogates?stage=s1&q=john&page=2')
    })

    it('preserves return_to while switching detail tabs', () => {
        mockDetailSearchParams.set('return_to', '/surrogates?stage=s1&q=john&page=2')

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        fireEvent.click(screen.getByRole('tab', { name: /Notes/i }))

        expect(mockReplace).toHaveBeenCalledWith(
            '/surrogates/c1/notes?return_to=%2Fsurrogates%3Fstage%3Ds1%26q%3Djohn%26page%3D2',
            { scroll: false },
        )
    })

    it('shows paused-from context in the detail header', () => {
        render(
            <SurrogateDetailHeader
                surrogateNumber="S12345"
                statusLabel="On-Hold"
                statusColor="#B4536A"
                pausedFromLabel="Ready to Match"
                isArchived={false}
                onBack={vi.fn()}
            />
        )

        expect(
            screen.getByText((_, element) => element?.textContent === 'Paused from: Ready to Match')
        ).toBeInTheDocument()
    })

    it('shows paused-from context in the detail layout when detail payload omits stage_slug', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                status_label: 'On-Hold',
                stage_id: 's4',
                stage_slug: undefined,
                stage_type: undefined,
                paused_from_stage_id: 's2',
                paused_from_stage_slug: 'ready_to_match',
                paused_from_stage_label: 'Ready to Match',
                paused_from_stage_type: 'post_approval',
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <div>Body</div>
            </SurrogateDetailLayoutClient>
        )

        expect(
            screen.getByText((_, element) => element?.textContent === 'Paused from: Ready to Match')
        ).toBeInTheDocument()
    })

    it('shows formatted height and BMI in demographics when height and weight are set', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                height_ft: 5.5,
                weight_lb: 120,
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        const bmiValue = Math.round((120 / ((5.5 * 12) ** 2)) * 703 * 10) / 10
        const heightRow = screen.getByText('Height:').parentElement
        expect(heightRow).toBeTruthy()
        expect(heightRow).toHaveTextContent('5 ft 6 in')
        expect(screen.getByText('BMI:')).toBeInTheDocument()
        expect(screen.getByText(String(bmiValue))).toBeInTheDocument()
    })

    it('shows "-" for height when missing but demographics section is visible', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                height_ft: null,
                weight_lb: 120,
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        const heightRow = screen.getByText('Height:').parentElement
        expect(heightRow).toBeTruthy()
        expect(heightRow).toHaveTextContent(/Height:\s*-/)
    })

    it('shows inline lead warning icons for affected fields and no review card', async () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                lead_intake_warnings: [
                    {
                        field_key: 'phone',
                        issue: 'missing_value',
                        raw_value: '555-CALL-NOW',
                    },
                    {
                        field_key: 'state',
                        issue: 'missing_value',
                        raw_value: 'Atlantis',
                    },
                    {
                        field_key: 'height_ft',
                        issue: 'missing_value',
                        raw_value: '5 ft 7 in',
                    },
                    {
                        field_key: 'weight_lb',
                        issue: 'missing_value',
                        raw_value: '140 lbs',
                    },
                ],
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.queryByTestId('lead-intake-review-card')).not.toBeInTheDocument()

        const phoneWarning = screen.getByLabelText('Phone lead intake warning')
        expect(phoneWarning).toBeInTheDocument()
        expect(phoneWarning).toHaveClass('dark:border-red-400/90')
        expect(phoneWarning).toHaveClass('dark:text-red-50')
        expect(screen.getByLabelText('State lead intake warning')).toBeInTheDocument()
        expect(screen.getByLabelText('Height lead intake warning')).toBeInTheDocument()
        expect(screen.getByLabelText('Weight lead intake warning')).toBeInTheDocument()
        expect(screen.queryByLabelText('Email lead intake warning')).not.toBeInTheDocument()

        const heightRow = screen.getByText('Height:').parentElement
        expect(heightRow).toBeTruthy()
        expect(heightRow).toHaveTextContent(/Height:\s*-/)

        const weightRow = screen.getByText('Weight:').parentElement
        expect(weightRow).toBeTruthy()
        expect(weightRow).toHaveTextContent(/Weight:\s*-/)

        fireEvent.focus(phoneWarning)

        await waitFor(() => {
            expect(screen.getByText('Phone')).toBeInTheDocument()
            expect(screen.getByText('This value could not be structured, so the field needs review.')).toBeInTheDocument()
            expect(screen.getByText('555-CALL-NOW')).toBeInTheDocument()
        })

        fireEvent.mouseEnter(screen.getByLabelText('State lead intake warning'))

        await waitFor(() => {
            expect(screen.getByText('State')).toBeInTheDocument()
            expect(screen.getByText('Atlantis')).toBeInTheDocument()
        })
    })

    it('shows email warning details in a tooltip on hover or focus', async () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                email: 'janeexample.com',
                lead_intake_warnings: [
                    {
                        field_key: 'email',
                        issue: 'invalid_value',
                        raw_value: 'jane@example,com',
                    },
                ],
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        const warningTrigger = screen.getByLabelText('Email lead intake warning')
        fireEvent.mouseEnter(warningTrigger)

        await waitFor(() => {
            expect(screen.getByText('Email')).toBeInTheDocument()
            expect(screen.getByText('This value could not be structured, so the field needs review.')).toBeInTheDocument()
            expect(screen.getByText('jane@example,com')).toBeInTheDocument()
        })

        const tooltipContent = screen.getByText('Raw lead value').closest('[data-slot="tooltip-content"]')
        expect(tooltipContent).toHaveClass('bg-white')
        expect(tooltipContent).toHaveClass('text-slate-950')
        expect(tooltipContent).toHaveClass('dark:bg-zinc-950')
    })

    it('computes BMI from rounded inches for decimal-feet height values', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                height_ft: 5.1,
                weight_lb: 180,
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        const heightRow = screen.getByText('Height:').parentElement
        expect(heightRow).toBeTruthy()
        expect(heightRow).toHaveTextContent('5 ft 1 in')
        expect(screen.getByText('BMI:')).toBeInTheDocument()
        expect(screen.getByText("34")).toBeInTheDocument()
    })

    it('shows formatted height when API returns numeric string height', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                // Runtime API payload can return Decimal values as strings.
                height_ft: '5.5' as unknown as number,
                weight_lb: 120,
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        const heightRow = screen.getByText('Height:').parentElement
        expect(heightRow).toBeTruthy()
        expect(heightRow).toHaveTextContent('5 ft 6 in')
    })

    it('shows 5 ft 0 in when API height is feet-only string', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                height_ft: '5' as unknown as number,
                weight_lb: 120,
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        const heightRow = screen.getByText('Height:').parentElement
        expect(heightRow).toBeTruthy()
        expect(heightRow).toHaveTextContent('5 ft 0 in')
    })

    it('shows Medical & Insurance but hides Pregnancy Tracker before ready_to_match', () => {
        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('Medical & Insurance')).toBeInTheDocument()
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

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('Medical & Insurance')).toBeInTheDocument()
        expect(screen.getByText('Pregnancy Tracker')).toBeInTheDocument()
        expect(screen.queryByText('Due Date:')).not.toBeInTheDocument()
    })

    it('shows Pregnancy Tracker when the heartbeat_confirmed slug is renamed', () => {
        mockPipelineStages = defaultPipelineStages.map((stage) =>
            stage.id === 's3' ? { ...stage, slug: 'heartbeat_logged' } : stage
        )
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                status_label: 'Heartbeat Confirmed',
                stage_id: 's3',
                stage_key: 'heartbeat_confirmed',
                stage_slug: 'heartbeat_logged',
                stage_type: 'post_approval',
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('Pregnancy Tracker')).toBeInTheDocument()
    })

    it('shows Resume action for surrogates currently on hold and resumes to paused-from stage', async () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                status_label: 'On-Hold',
                stage_id: 's4',
                stage_slug: 'on_hold',
                stage_type: 'paused',
                paused_from_stage_id: 's2',
                paused_from_stage_slug: 'ready_to_match',
                paused_from_stage_label: 'Ready to Match',
                paused_from_stage_type: 'post_approval',
            },
            isLoading: false,
            error: null,
        })
        mockChangeStatus.mockReturnValue(new Promise(() => {}))

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        fireEvent.click(screen.getByRole('button', { name: 'Resume' }))

        await waitFor(() => {
            expect(mockChangeStatus).toHaveBeenCalledWith({
                surrogateId: 'c1',
                data: { stage_id: 's2' },
            })
        })
    })

    it('shows Medical & Insurance but hides Pregnancy Tracker for on-hold with intake stage', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                status_label: 'On-Hold',
                stage_id: 's4',
                stage_slug: 'on_hold',
                stage_type: 'paused',
                paused_from_stage_id: 's1',
                paused_from_stage_slug: 'new_unread',
                paused_from_stage_label: 'New Unread',
                paused_from_stage_type: 'intake',
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('Medical & Insurance')).toBeInTheDocument()
        expect(screen.queryByText('Pregnancy Tracker')).not.toBeInTheDocument()
    })

    it('saves PCP name edits to pcp_name after adding the section from Edit Info', async () => {
        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        mockUpdateSurrogate.mockClear()

        fireEvent.click(screen.getByRole('button', { name: /edit info/i }))
        fireEvent.click(screen.getByRole('menuitem', { name: /add section/i }))
        fireEvent.click(screen.getByRole('menuitem', { name: /pcp provider/i }))
        fireEvent.click(screen.getByRole('button', { name: 'Edit Clinic/Hospital name' }))
        fireEvent.change(screen.getByLabelText('Clinic/Hospital name'), {
            target: { value: 'Austin PCP Associates' },
        })
        fireEvent.keyDown(screen.getByLabelText('Clinic/Hospital name'), { key: 'Enter' })

        await waitFor(() => {
            expect(mockUpdateSurrogate).toHaveBeenCalledWith({
                surrogateId: 'c1',
                data: { pcp_name: 'Austin PCP Associates' },
            })
        })
    })

    it('shows persisted medical sections automatically when hidden address fields contain data', () => {
        mockUseSurrogate.mockReturnValue({
            data: {
                ...baseSurrogateData,
                pcp_state: 'TX',
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('PCP Provider')).toBeInTheDocument()
    })

    it('allows deleting a visible section from Edit Info with confirmation', async () => {
        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        mockUpdateSurrogate.mockClear()

        fireEvent.click(screen.getByRole('button', { name: /edit info/i }))
        fireEvent.click(screen.getByRole('menuitem', { name: /add section/i }))
        fireEvent.click(screen.getByRole('menuitem', { name: /pcp provider/i }))
        expect(screen.getByText('PCP Provider')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /edit info/i }))
        fireEvent.click(screen.getByRole('menuitem', { name: /delete section/i }))
        fireEvent.click(screen.getByRole('menuitem', { name: /delete pcp provider/i }))

        expect(screen.getByText('Delete PCP Provider section?')).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
        expect(mockUpdateSurrogate).not.toHaveBeenCalled()
        expect(screen.getByText('PCP Provider')).toBeInTheDocument()

        fireEvent.click(screen.getByRole('button', { name: /edit info/i }))
        fireEvent.click(screen.getByRole('menuitem', { name: /delete section/i }))
        fireEvent.click(screen.getByRole('menuitem', { name: /delete pcp provider/i }))
        fireEvent.click(screen.getByRole('button', { name: 'Delete Section' }))

        await waitFor(() => {
            expect(mockUpdateSurrogate).toHaveBeenCalledWith({
                surrogateId: 'c1',
                data: {
                    pcp_provider_name: null,
                    pcp_name: null,
                    pcp_address_line1: null,
                    pcp_address_line2: null,
                    pcp_city: null,
                    pcp_state: null,
                    pcp_postal: null,
                    pcp_phone: null,
                    pcp_fax: null,
                    pcp_email: null,
                },
            })
        })

        await waitFor(() => {
            expect(screen.queryByText('PCP Provider')).not.toBeInTheDocument()
        })
    })

    it('keeps journey hidden for on-hold surrogates paused before match', () => {
        mockSegment.value = 'journey'
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                status_label: 'On-Hold',
                stage_id: 's4',
                stage_slug: 'on_hold',
                stage_type: 'paused',
                paused_from_stage_id: 's1',
                paused_from_stage_slug: 'new_unread',
                paused_from_stage_label: 'New Unread',
                paused_from_stage_type: 'intake',
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateJourneyPage />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('No journey available yet')).toBeInTheDocument()
        expect(screen.queryByText('Journey timeline for c1')).not.toBeInTheDocument()
    })

    it.each([
        { statusLabel: 'Disqualified', stageId: 's6', stageSlug: 'disqualified' as const },
        { statusLabel: 'Lost', stageId: 's5', stageSlug: 'lost' as const },
    ])('hides Pregnancy Tracker for terminal stage: $statusLabel', ({ statusLabel, stageId, stageSlug }) => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                status_label: statusLabel,
                stage_id: stageId,
                stage_slug: stageSlug,
                stage_type: 'terminal',
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.queryByText('Pregnancy Tracker')).not.toBeInTheDocument()
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

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('Pregnancy Tracker')).toBeInTheDocument()
        expect(screen.getByText('Due Date:')).toBeInTheDocument()
    })

    it('shows Actual Delivery Date row when delivery date is set', () => {
        mockUseSurrogate.mockReturnValueOnce({
            data: {
                ...baseSurrogateData,
                status_label: 'Heartbeat Confirmed',
                stage_id: 's3',
                stage_slug: 'heartbeat_confirmed',
                stage_type: 'post_approval',
                pregnancy_start_date: '2025-01-10',
                pregnancy_due_date: '2025-10-17',
                actual_delivery_date: '2025-10-20',
                delivery_baby_gender: 'Female',
                delivery_baby_weight: '7 lb 2 oz',
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText('Pregnancy Tracker')).toBeInTheDocument()
        expect(screen.getByText('Actual Delivery Date:')).toBeInTheDocument()
        expect(screen.getByText('Gender:')).toBeInTheDocument()
        expect(screen.getByText('Weight:')).toBeInTheDocument()
    })

    it('renders the API-provided eligibility checklist instead of hard-coded rows', () => {
        mockUseSurrogate.mockReturnValue({
            data: {
                ...baseSurrogateData,
                has_surrogate_experience: true,
                eligibility_checklist: [
                    {
                        key: 'is_age_eligible',
                        label: 'Age Eligible (21-36)',
                        type: 'boolean',
                        value: true,
                        display_value: 'Yes',
                    },
                    {
                        key: 'journey_timing_preference',
                        label: 'Journey Timing',
                        type: 'text',
                        value: 'months_0_3',
                        display_value: '0–3 months',
                    },
                ],
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        expect(screen.getByText(/Journey Timing/)).toBeInTheDocument()
        expect(screen.getByText('0–3 months')).toBeInTheDocument()
        expect(screen.queryByText('Prior Surrogate Experience')).not.toBeInTheDocument()
    })

    it('keeps visible checklist items editable from the surrogate detail edit dialog', async () => {
        mockUseSurrogate.mockReturnValue({
            data: {
                ...baseSurrogateData,
                is_age_eligible: true,
                journey_timing_preference: 'months_0_3',
                num_deliveries: 1,
                eligibility_checklist: [
                    {
                        key: 'is_age_eligible',
                        label: 'Age Eligible (21-36)',
                        type: 'boolean',
                        value: true,
                        display_value: 'Yes',
                    },
                    {
                        key: 'journey_timing_preference',
                        label: 'Journey Timing',
                        type: 'text',
                        value: 'months_0_3',
                        display_value: '0–3 months',
                    },
                    {
                        key: 'num_deliveries',
                        label: 'Number of Deliveries',
                        type: 'number',
                        value: 1,
                        display_value: '1',
                    },
                ],
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        mockUpdateSurrogate.mockClear()

        fireEvent.click(screen.getByRole('button', { name: /more actions/i }))
        fireEvent.click(screen.getByRole('menuitem', { name: /^edit$/i }))

        const journeyTimingSelect = await screen.findByLabelText('Journey Timing')
        expect(journeyTimingSelect).toHaveValue('months_0_3')
        expect(screen.getByLabelText('Number of Deliveries')).toHaveValue(1)
        expect(screen.queryByLabelText('Surrogate Experience')).not.toBeInTheDocument()

        fireEvent.change(journeyTimingSelect, { target: { value: 'still_deciding' } })
        fireEvent.change(screen.getByLabelText('Number of Deliveries'), { target: { value: '2' } })
        fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))

        await waitFor(() => {
            expect(mockUpdateSurrogate).toHaveBeenCalledWith({
                surrogateId: 'c1',
                data: expect.objectContaining({
                    journey_timing_preference: 'still_deciding',
                    num_deliveries: 2,
                }),
            })
        })
    })

    it('edits height with feet and inches controls and saves canonical decimal feet', async () => {
        mockUseSurrogate.mockReturnValue({
            data: {
                ...baseSurrogateData,
                height_ft: 4.92,
            },
            isLoading: false,
            error: null,
        })

        render(
            <SurrogateDetailLayoutClient>
                <SurrogateOverviewTab />
            </SurrogateDetailLayoutClient>
        )

        mockUpdateSurrogate.mockClear()

        fireEvent.click(screen.getByRole('button', { name: /more actions/i }))
        fireEvent.click(screen.getByRole('menuitem', { name: /^edit$/i }))

        const feetSelect = await screen.findByLabelText('Height Feet')
        const inchesSelect = screen.getByLabelText('Height Inches')

        expect(feetSelect).toHaveValue('4')
        expect(inchesSelect).toHaveValue('11')

        fireEvent.change(feetSelect, { target: { value: '4' } })
        fireEvent.change(inchesSelect, { target: { value: '11' } })
        fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))

        await waitFor(() => {
            expect(mockUpdateSurrogate).toHaveBeenCalledWith({
                surrogateId: 'c1',
                data: expect.objectContaining({
                    height_ft: 4.92,
                }),
            })
        })
    })
})
