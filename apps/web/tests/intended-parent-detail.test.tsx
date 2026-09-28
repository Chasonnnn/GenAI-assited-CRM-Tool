import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import IntendedParentDetailPage from '../app/(app)/intended-parents/[id]/page'
import { ApiError } from '@/lib/api'

const mockPush = vi.fn()
const mockUpdateIntendedParent = vi.fn()
const mockArchiveIntendedParent = vi.fn()
const mockDeleteIntendedParent = vi.fn()
const mockUseIntendedParentHistory = vi.fn()
const mockUseIntendedParentNotes = vi.fn()
const mockUseTasks = vi.fn()
const mockUseIPAttachments = vi.fn()
const mockUseEntityActivity = vi.fn()
const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
const mockUseIntendedParentStatuses = vi.fn()
const mockUpdateIntendedParentStatus = vi.fn()

const DEFAULT_PERMISSIONS = ["edit_intended_parents", "view_tasks", "create_tasks", "edit_tasks", "delete_tasks"]

function stageSemantics(overrides: Record<string, unknown> = {}) {
    return {
        capabilities: {
            counts_as_contacted: false,
            eligible_for_matching: false,
            locks_match_state: false,
            shows_pregnancy_tracking: false,
            requires_delivery_details: false,
            tracks_interview_outcome: false,
        },
        pause_behavior: "none",
        terminal_outcome: "none",
        integration_bucket: "none",
        analytics_bucket: null,
        suggestion_profile_key: null,
        requires_reason_on_enter: false,
        ...overrides,
    }
}

const IP_STAGE_STATUSES = [
    {
        id: 'stage-new',
        value: 'new',
        label: 'New',
        stage_key: 'new',
        stage_slug: 'new',
        stage_type: 'intake',
        color: '#3B82F6',
        order: 1,
        semantics: stageSemantics(),
    },
    {
        id: 'stage-ready',
        value: 'ready_to_match',
        label: 'Ready to Match',
        stage_key: 'ready_to_match',
        stage_slug: 'ready_to_match',
        stage_type: 'post_approval',
        color: '#F59E0B',
        order: 2,
        semantics: stageSemantics({ capabilities: { ...stageSemantics().capabilities, eligible_for_matching: true } }),
    },
    {
        id: 'stage-matched',
        value: 'matched',
        label: 'Matched',
        stage_key: 'matched',
        stage_slug: 'matched',
        stage_type: 'post_approval',
        color: '#10B981',
        order: 3,
        semantics: stageSemantics({ capabilities: { ...stageSemantics().capabilities, locks_match_state: true } }),
    },
]

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: ({ content, onChange, ariaLabel }: { content: string; onChange: (html: string) => void; ariaLabel: string }) => <textarea aria-label={ariaLabel} value={content} onChange={(event) => onChange(event.target.value)} />,
}))
vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock('next/navigation', () => ({
    useParams: () => ({ id: 'ip1' }),
    useRouter: () => ({ push: mockPush }),
}))

vi.mock('@/lib/auth-context', () => ({
    useAuth: () => mockUseAuth(),
}))

const mockUseIntendedParent = vi.fn()

vi.mock('@/lib/hooks/use-intended-parents', () => ({
    useIntendedParent: (id: string) => mockUseIntendedParent(id),
    useIntendedParentHistory: (id: string | null) => mockUseIntendedParentHistory(id),
    useIntendedParentNotes: () => mockUseIntendedParentNotes(),
    useUpdateIntendedParent: () => ({ mutateAsync: mockUpdateIntendedParent, isPending: false }),
    useUpdateIntendedParentStatus: () => ({ mutateAsync: mockUpdateIntendedParentStatus, isPending: false }),
    useArchiveIntendedParent: () => ({ mutateAsync: mockArchiveIntendedParent, isPending: false }),
    useRestoreIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteIntendedParent: () => ({ mutateAsync: mockDeleteIntendedParent, isPending: false }),
    useCreateIntendedParentNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteIntendedParentNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/hooks/use-metadata', () => ({
    useIntendedParentStatuses: () => mockUseIntendedParentStatuses(),
}))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useCreateTask: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCreateTaskBatch: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateTask: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCompleteTask: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUncompleteTask: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteTask: () => ({ mutateAsync: vi.fn(), isPending: false }),

    useTasks: (...args: unknown[]) => mockUseTasks(...args),
}))

vi.mock('@/lib/hooks/use-entity-activity', () => ({
    useEntityActivity: (...args: unknown[]) => mockUseEntityActivity(...args),
}))

vi.mock('@/lib/hooks/use-attachments', () => ({
    useUploadIPAttachment: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteIPAttachment: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDownloadAttachment: () => ({ mutateAsync: vi.fn(), isPending: false }),

    useIPAttachments: (...args: unknown[]) => mockUseIPAttachments(...args),
}))

function setUser(role: string, permissions: string[]) {
    mockUseAuth.mockReturnValue({
        user: { role, user_id: 'user-1' },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
    })
    mockUseEffectivePermissions.mockReturnValue({ data: { permissions } })
}

describe('IntendedParentDetailPage', () => {
    beforeEach(() => {
        setUser('developer', DEFAULT_PERMISSIONS)
        mockUseIntendedParentStatuses.mockReturnValue({
            data: { statuses: IP_STAGE_STATUSES },
            isLoading: false,
            isError: false,
            isFetching: false,
            refetch: vi.fn(),
        })
        mockUpdateIntendedParentStatus.mockReset()
        mockUpdateIntendedParentStatus.mockResolvedValue({ status: 'applied' })
        mockUpdateIntendedParent.mockReset()
        mockUpdateIntendedParent.mockResolvedValue({})
        mockUseIntendedParentHistory.mockReturnValue({ data: [] })
        mockUseIntendedParentNotes.mockReturnValue({ data: [] })
        mockUseTasks.mockReturnValue({ data: { items: [] } })
        mockUseIPAttachments.mockReturnValue({ data: [] })
        mockUseEntityActivity.mockReturnValue({
            data: { items: [], total: 0, page: 1, pages: 1 },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        mockUseIntendedParent.mockReturnValue({
            data: {
                id: 'ip1',
                full_name: 'Bob Parent',
                email: 'bob@example.com',
                phone: null,
                state: 'CA',
                budget: 50000,
                notes_internal: null,
                pronouns: null,
                date_of_birth: '1989-05-15',
                marital_status: 'Married',
                partner_name: 'Pat Parent',
                partner_email: 'pat@example.com',
                partner_pronouns: 'They/Them',
                partner_date_of_birth: '1991-08-09',
                address_line1: '123 Main St',
                address_line2: 'Unit 4',
                city: 'Austin',
                postal: '78701',
                ip_clinic_name: 'RMA Austin',
                ip_clinic_address_line1: '500 Clinic Way',
                ip_clinic_address_line2: null,
                ip_clinic_city: 'Austin',
                ip_clinic_state: 'TX',
                ip_clinic_postal: '78702',
                ip_clinic_phone: '+15125550123',
                ip_clinic_fax: '+15125550124',
                ip_clinic_email: 'intake@rmaaustin.com',
                embryo_count: 4,
                pgs_tested: true,
                egg_source: 'intended_mother',
                sperm_source: 'sperm_donor',
                trust_provider_name: 'North Star Trust',
                trust_primary_contact_name: 'Avery Chen',
                trust_email: 'contact@northstartrust.com',
                trust_phone: '+15125550130',
                trust_address_line1: '700 Trust Ave',
                trust_address_line2: 'Suite 200',
                trust_city: 'Austin',
                trust_state: 'TX',
                trust_postal: '78703',
                trust_case_reference: 'NST-2049',
                trust_funding_status: 'funded',
                trust_portal_url: 'https://portal.northstartrust.com/cases/nst-2049',
                trust_notes: 'Monthly replenishment review.',
                status: 'new',
                stage_id: 'stage-new',
                stage_key: 'new',
                stage_slug: 'new',
                status_label: 'New',
                owner_type: null,
                owner_id: null,
                owner_name: null,
                is_archived: false,
                archived_at: null,
                last_activity: new Date().toISOString(),
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
            isLoading: false,
            error: null,
        })
    })

    it('renders intended-parent identity, controls, and medical details', () => {
        render(<IntendedParentDetailPage />)
        expect(screen.getByText('Bob Parent')).toBeInTheDocument()
        expect(screen.getAllByText('bob@example.com').length).toBeGreaterThan(0)
        expect(screen.getByRole("link", { name: "Back to intended parents" })).toBeInTheDocument()
        expect(
            screen.getByRole("button", { name: "Actions for Bob Parent" })
        ).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Change Stage" })).toBeInTheDocument()
        expect(screen.queryByRole("heading", { name: "Status" })).not.toBeInTheDocument()
        expect(screen.getByText("Activity")).toBeInTheDocument()
        expect(screen.queryByText("Stage History")).not.toBeInTheDocument()
        expect(screen.queryByText("Created:")).not.toBeInTheDocument()
        expect(screen.queryByText("Last Activity:")).not.toBeInTheDocument()
        expect(screen.getByText("Marital Status")).toBeInTheDocument()
        expect(screen.getByText("Married")).toBeInTheDocument()
        expect(screen.getByText("May 15, 1989")).toBeInTheDocument()
        expect(screen.getByText("Aug 9, 1991")).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "Embryo Status" })).toBeInTheDocument()
        expect(screen.getByText("Intended Mother")).toBeInTheDocument()
        expect(screen.getByText("Sperm Donor")).toBeInTheDocument()
        expect(screen.getByText("Yes")).toBeInTheDocument()
        expect(screen.getByTestId("ip-medical-sections-grid")).toHaveClass("grid", "gap-4", "md:grid-cols-2")
    })

    it("sanitizes intended-parent note HTML at the render boundary", () => {
        mockUseIntendedParentNotes.mockReturnValueOnce({
            data: [
                {
                    id: "note-xss",
                    author_id: "user-1",
                    content: '<img src=x onerror="alert(1)"><p>Safe note</p><script>alert("x")</script>',
                    created_at: "2026-02-25T21:46:00Z",
                },
            ],
        })

        const { container } = render(<IntendedParentDetailPage />)

        expect(screen.getByText("Safe note")).toBeInTheDocument()
        expect(container.querySelector("img")).toBeNull()
        expect(container.querySelector("script")).toBeNull()
        expect(container.querySelector("[onerror]")).toBeNull()
    })

    it("confirms archive and permanent delete in app dialogs that name the record", async () => {
        const confirmSpy = vi.spyOn(window, "confirm")
        const current = mockUseIntendedParent("ip1").data
        mockUseIntendedParent.mockReturnValue({
            data: { ...current, intended_parent_number: "I10001" },
            isLoading: false,
            error: null,
        })
        mockArchiveIntendedParent.mockResolvedValue({})
        const view = render(<IntendedParentDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Actions for Bob Parent" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: /archive/i }))
        const archiveDialog = await screen.findByRole("alertdialog", { name: "Archive intended parent I10001?" })
        expect(mockArchiveIntendedParent).not.toHaveBeenCalled()
        fireEvent.click(within(archiveDialog).getByRole("button", { name: "Archive intended parent" }))
        await waitFor(() => expect(mockArchiveIntendedParent).toHaveBeenCalledWith("ip1"))

        mockUseIntendedParent.mockReturnValue({
            data: { ...current, intended_parent_number: "I10001", is_archived: true },
            isLoading: false,
            error: null,
        })
        mockDeleteIntendedParent.mockResolvedValue({})
        view.rerender(<IntendedParentDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Actions for Bob Parent" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: /delete permanently/i }))
        const deleteDialog = await screen.findByRole("alertdialog", { name: "Delete intended parent I10001?" })
        fireEvent.click(within(deleteDialog).getByRole("button", { name: "Delete I10001" }))
        await waitFor(() => expect(mockDeleteIntendedParent).toHaveBeenCalledWith("ip1"))
        await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/intended-parents"))
        expect(confirmSpy).not.toHaveBeenCalled()
        confirmSpy.mockRestore()
    })

    it("renders intended-parent activity in the same staged journey format as surrogate details", () => {
        mockUseEntityActivity.mockReturnValueOnce({
            data: {
                items: [
                    {
                        id: "note-activity-1",
                        activity_type: "note_added",
                        actor_user_id: "user-1",
                        actor_name: "Test Developer",
                        details: { preview: "Profile reviewed." },
                        created_at: "2026-02-25T21:46:00Z",
                    },
                    {
                        id: "attachment-activity-1",
                        activity_type: "attachment_added",
                        actor_user_id: "user-1",
                        actor_name: "Test Developer",
                        details: { filename: "Legal packet.pdf" },
                        created_at: "2026-02-26T21:46:00Z",
                    },
                ],
                total: 2,
                page: 1,
                pages: 1,
            },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        mockUseIntendedParentHistory.mockReturnValueOnce({
            data: [
                {
                    id: "hist-1",
                    old_stage_id: null,
                    new_stage_id: "stage-new",
                    old_status: null,
                    new_status: "new",
                    reason: null,
                    changed_by_user_id: "user-1",
                    changed_by_name: "Test Developer",
                    changed_at: "2026-02-24T21:46:00Z",
                    effective_at: "2026-02-24T21:46:00Z",
                    recorded_at: "2026-02-24T21:46:00Z",
                    requested_at: null,
                    approved_by_user_id: null,
                    approved_by_name: null,
                    approved_at: null,
                    is_undo: false,
                    request_id: null,
                },
            ],
        })
        mockUseIntendedParentNotes.mockReturnValueOnce({
            data: [
                {
                    id: "note-1",
                    author_id: "user-1",
                    content: "<p>Profile reviewed.</p>",
                    created_at: "2026-02-25T21:46:00Z",
                },
            ],
        })
        mockUseTasks.mockReturnValueOnce({
            data: {
                items: [
                    {
                        id: "task-1",
                        title: "Confirm embryo paperwork",
                        description: null,
                        task_type: "follow_up",
                        surrogate_id: null,
                        intended_parent_id: "ip1",
                        surrogate_number: null,
                        owner_type: "user",
                        owner_id: "user-1",
                        owner_name: "Owner",
                        created_by_user_id: "user-1",
                        created_by_name: "Owner",
                        due_date: "2026-03-01",
                        due_time: null,
                        duration_minutes: null,
                        is_completed: false,
                        status: "pending",
                        workflow_action_type: null,
                        workflow_action_preview: null,
                        due_at: null,
                        completed_at: null,
                        completed_by_name: null,
                        created_at: "2026-02-20T21:46:00Z",
                    },
                ],
            },
        })

        render(<IntendedParentDetailPage />)

        const activityCard = screen.getByText("Activity").closest('[data-slot="card"]')
        expect(activityCard).toBeTruthy()

        const activity = within(activityCard!)
        expect(activity.getByText("Entered stage")).toBeInTheDocument()
        expect(activity.getByText("Note")).toBeInTheDocument()
        expect(activity.getByText("Profile reviewed.")).toBeInTheDocument()
        expect(activity.getByText("File uploaded")).toBeInTheDocument()
        expect(activity.getByText("Legal packet.pdf")).toBeInTheDocument()
        expect(activity.getByText("Next Steps")).toBeInTheDocument()
        expect(activity.getByText("Confirm embryo paperwork")).toBeInTheDocument()
    })

    it("renders partner details above marital status in the detail tab", () => {
        render(<IntendedParentDetailPage />)

        const partnerCardTitle = screen.getByText("Partner")
        const maritalStatusCardTitle = screen.getByText("Marital Status")

        expect(
            partnerCardTitle.compareDocumentPosition(maritalStatusCardTitle) &
                Node.DOCUMENT_POSITION_FOLLOWING
        ).toBeTruthy()
    })

    it("renders fixed trust info on the detail page", () => {
        render(<IntendedParentDetailPage />)

        const trustInfoCard = screen.getByText("Trust Info").closest('[data-slot="card"]')
        expect(trustInfoCard).toBeTruthy()

        const card = within(trustInfoCard!)
        expect(card.getByText("Provider")).toBeInTheDocument()
        expect(card.getByText("Primary Contact")).toBeInTheDocument()
        expect(card.getByText("Email")).toBeInTheDocument()
        expect(card.getByText("Phone")).toBeInTheDocument()
        expect(card.getByText("Reference ID")).toBeInTheDocument()
        expect(card.getByText("Funding Status")).toBeInTheDocument()
        expect(card.getByText("Portal URL")).toBeInTheDocument()
        expect(card.getByText("Notes")).toBeInTheDocument()
        expect(card.getByText("Address")).toBeInTheDocument()
        expect(card.getByText("North Star Trust")).toBeInTheDocument()
        expect(card.getByText("Avery Chen")).toBeInTheDocument()
        expect(card.getByText("contact@northstartrust.com")).toBeInTheDocument()
        expect(card.getByText("+15125550130")).toBeInTheDocument()
        expect(card.getByText("NST-2049")).toBeInTheDocument()
        expect(card.getByText("Funded")).toBeInTheDocument()
        expect(card.getByText("https://portal.northstartrust.com/cases/nst-2049")).toBeInTheDocument()
        expect(card.getByText("Monthly replenishment review.")).toBeInTheDocument()
        expect(card.getByText("700 Trust Ave, Suite 200, Austin, TX, 78703")).toBeInTheDocument()
        expect(card.queryByText("Line 1:")).not.toBeInTheDocument()
        expect(card.queryByText("Line 2:")).not.toBeInTheDocument()
    })

    it("updates marital status from fixed options on the detail page", async () => {
        render(<IntendedParentDetailPage />)

        const maritalStatusSelect = screen.getByRole("combobox", { name: "Marital status" })
        fireEvent.mouseDown(maritalStatusSelect)
        const partneredOption = await screen.findByRole("option", { name: "Partnered" })
        fireEvent.mouseMove(partneredOption)
        fireEvent.click(partneredOption)

        await waitFor(() => {
            expect(mockUpdateIntendedParent).toHaveBeenCalledWith({
                id: "ip1",
                data: { marital_status: "Partnered" },
            })
        })
    })

    it("updates trust provider info inline from the detail page", async () => {
        render(<IntendedParentDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Edit Trust provider" }))
        fireEvent.change(screen.getByLabelText("Trust provider"), {
            target: { value: "Evergreen Trust" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save Trust provider" }))

        await waitFor(() => {
            expect(mockUpdateIntendedParent).toHaveBeenCalledWith({
                id: "ip1",
                data: { trust_provider_name: "Evergreen Trust" },
            })
        })
    })

    it("updates trust address from the detail page", async () => {
        render(<IntendedParentDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Edit Trust address" }))
        fireEvent.change(screen.getByLabelText("Trust address line 1"), {
            target: { value: "44 Escrow Blvd" },
        })
        fireEvent.change(screen.getByLabelText("Trust city"), {
            target: { value: "Dallas" },
        })
        fireEvent.change(screen.getByLabelText("Trust state"), {
            target: { value: "TX" },
        })
        fireEvent.change(screen.getByLabelText("Trust ZIP"), {
            target: { value: "75201" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save Trust address" }))

        await waitFor(() => {
            expect(mockUpdateIntendedParent).toHaveBeenCalledWith({
                id: "ip1",
                data: {
                    trust_address_line1: "44 Escrow Blvd",
                    trust_address_line2: "Suite 200",
                    trust_city: "Dallas",
                    trust_state: "TX",
                    trust_postal: "75201",
                },
            })
        })
    })

    it("updates trust funding status from fixed options on the detail page", async () => {
        render(<IntendedParentDetailPage />)

        fireEvent.mouseDown(screen.getByRole("combobox", { name: "Trust funding status" }))
        const replenishmentOption = await screen.findByRole("option", { name: "Needs Replenishment" })
        fireEvent.mouseMove(replenishmentOption)
        fireEvent.click(replenishmentOption)

        await waitFor(() => {
            expect(mockUpdateIntendedParent).toHaveBeenCalledWith({
                id: "ip1",
                data: { trust_funding_status: "needs_replenishment" },
            })
        })
    })

    it("shows the partner card when only partner DOB is present", () => {
        mockUseIntendedParent.mockReturnValueOnce({
            data: {
                id: 'ip1',
                full_name: 'Bob Parent',
                email: 'bob@example.com',
                phone: null,
                state: 'CA',
                budget: 50000,
                notes_internal: null,
                pronouns: null,
                date_of_birth: '1989-05-15',
                marital_status: null,
                partner_name: null,
                partner_email: null,
                partner_pronouns: null,
                partner_date_of_birth: '1991-07-09',
                address_line1: '123 Main St',
                address_line2: null,
                city: 'Austin',
                postal: '78701',
                ip_clinic_name: null,
                ip_clinic_address_line1: null,
                ip_clinic_address_line2: null,
                ip_clinic_city: null,
                ip_clinic_state: null,
                ip_clinic_postal: null,
                ip_clinic_phone: null,
                ip_clinic_fax: null,
                ip_clinic_email: null,
                embryo_count: null,
                pgs_tested: null,
                egg_source: null,
                sperm_source: null,
                trust_provider_name: null,
                trust_primary_contact_name: null,
                trust_email: null,
                trust_phone: null,
                trust_address_line1: null,
                trust_address_line2: null,
                trust_city: null,
                trust_state: null,
                trust_postal: null,
                trust_case_reference: null,
                trust_funding_status: null,
                trust_portal_url: null,
                trust_notes: null,
                status: 'new',
                stage_id: 'stage-new',
                stage_key: 'new',
                stage_slug: 'new',
                status_label: 'New',
                owner_type: null,
                owner_id: null,
                owner_name: null,
                is_archived: false,
                archived_at: null,
                last_activity: new Date().toISOString(),
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
            isLoading: false,
            error: null,
        })

        render(<IntendedParentDetailPage />)

        expect(screen.getByText("Partner")).toBeInTheDocument()
        expect(screen.getByText("Jul 9, 1991")).toBeInTheDocument()
    })

    it("keeps IVF clinic fields out of the edit dialog", () => {
        render(<IntendedParentDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Actions for Bob Parent" }))
        fireEvent.click(screen.getByRole("menuitem", { name: "Edit" }))
        const dialog = screen.getByRole("dialog")

        expect(within(dialog).getByLabelText(/partner email/i)).toBeInTheDocument()
        expect(within(dialog).getByLabelText(/partner pronouns/i)).toBeInTheDocument()
        expect(within(dialog).getByLabelText(/address line 1/i)).toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/ivf clinic name/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/ivf clinic email/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/internal notes/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/date of birth/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/marital status/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/number of embryos/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/pgs tested/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/egg source/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/sperm source/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/trust info/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/trust provider/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/primary contact/i)).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/portal url/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/budget/i)).not.toBeInTheDocument()
    })

    it("edits IVF clinic details from the detail card instead of the edit dialog", async () => {
        render(<IntendedParentDetailPage />)

        expect(screen.getByRole("button", { name: "Edit Info" })).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "IVF Clinic" })).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Edit IVF Clinic name" }))
        fireEvent.change(screen.getByLabelText("IVF Clinic name"), {
            target: { value: "CCRM Austin" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save IVF Clinic name" }))

        await waitFor(() => {
            expect(mockUpdateIntendedParent).toHaveBeenCalledWith({
                id: "ip1",
                data: { ip_clinic_name: "CCRM Austin" },
            })
        })
    })

    it("keeps IVF clinic hidden until it is added from Edit Info", async () => {
        mockUseIntendedParent.mockReturnValueOnce({
            data: {
                id: 'ip1',
                full_name: 'Bob Parent',
                email: 'bob@example.com',
                phone: null,
                state: 'CA',
                budget: 50000,
                notes_internal: 'Initial inquiry via referral.',
                pronouns: null,
                date_of_birth: null,
                marital_status: null,
                partner_name: 'Pat Parent',
                partner_email: 'pat@example.com',
                partner_pronouns: 'They/Them',
                partner_date_of_birth: null,
                address_line1: '123 Main St',
                address_line2: 'Unit 4',
                city: 'Austin',
                postal: '78701',
                ip_clinic_name: null,
                ip_clinic_address_line1: null,
                ip_clinic_address_line2: null,
                ip_clinic_city: null,
                ip_clinic_state: null,
                ip_clinic_postal: null,
                ip_clinic_phone: null,
                ip_clinic_fax: null,
                ip_clinic_email: null,
                embryo_count: null,
                pgs_tested: null,
                egg_source: null,
                sperm_source: null,
                trust_provider_name: null,
                trust_primary_contact_name: null,
                trust_email: null,
                trust_phone: null,
                trust_address_line1: null,
                trust_address_line2: null,
                trust_city: null,
                trust_state: null,
                trust_postal: null,
                trust_case_reference: null,
                trust_funding_status: null,
                trust_portal_url: null,
                trust_notes: null,
                status: 'new',
                stage_id: 'stage-new',
                stage_key: 'new',
                stage_slug: 'new',
                status_label: 'New',
                owner_type: null,
                owner_id: null,
                owner_name: null,
                is_archived: false,
                archived_at: null,
                last_activity: new Date().toISOString(),
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
            isLoading: false,
            error: null,
        })

        render(<IntendedParentDetailPage />)

        expect(screen.queryByRole("heading", { name: "IVF Clinic" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Edit Info" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: /add section/i }))
        fireEvent.click(await screen.findByRole("menuitem", { name: /ivf clinic/i }))

        await waitFor(() => {
            expect(screen.getByRole("heading", { name: "IVF Clinic" })).toBeInTheDocument()
        })
    })

    it("adds and removes embryo status from medical information", async () => {
        mockUseIntendedParent.mockReturnValueOnce({
            data: {
                id: 'ip1',
                full_name: 'Bob Parent',
                email: 'bob@example.com',
                phone: null,
                state: 'CA',
                budget: 50000,
                notes_internal: null,
                pronouns: null,
                date_of_birth: '1989-05-15',
                marital_status: 'Married',
                partner_name: 'Pat Parent',
                partner_email: 'pat@example.com',
                partner_pronouns: 'They/Them',
                partner_date_of_birth: '1991-08-09',
                address_line1: '123 Main St',
                address_line2: null,
                city: 'Austin',
                postal: '78701',
                ip_clinic_name: null,
                ip_clinic_address_line1: null,
                ip_clinic_address_line2: null,
                ip_clinic_city: null,
                ip_clinic_state: null,
                ip_clinic_postal: null,
                ip_clinic_phone: null,
                ip_clinic_fax: null,
                ip_clinic_email: null,
                embryo_count: null,
                pgs_tested: null,
                egg_source: null,
                sperm_source: null,
                trust_provider_name: null,
                trust_primary_contact_name: null,
                trust_email: null,
                trust_phone: null,
                trust_address_line1: null,
                trust_address_line2: null,
                trust_city: null,
                trust_state: null,
                trust_postal: null,
                trust_case_reference: null,
                trust_funding_status: null,
                trust_portal_url: null,
                trust_notes: null,
                status: 'new',
                stage_id: 'stage-new',
                stage_key: 'new',
                stage_slug: 'new',
                status_label: 'New',
                owner_type: null,
                owner_id: null,
                owner_name: null,
                is_archived: false,
                archived_at: null,
                last_activity: new Date().toISOString(),
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
            isLoading: false,
            error: null,
        })

        render(<IntendedParentDetailPage />)

        expect(screen.queryByRole("heading", { name: "Embryo Status" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Edit Info" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: /add section/i }))
        fireEvent.click(await screen.findByRole("menuitem", { name: /embryo status/i }))

        expect(screen.getByRole("heading", { name: "Embryo Status" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Edit Info" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: /delete section/i }))
        fireEvent.click(await screen.findByRole("menuitem", { name: /delete embryo status/i }))
        fireEvent.click(screen.getByRole("button", { name: "Delete Section" }))

        await waitFor(() => {
            expect(mockUpdateIntendedParent).toHaveBeenCalledWith({
                id: "ip1",
                data: {
                    embryo_count: null,
                    pgs_tested: null,
                    egg_source: null,
                    sperm_source: null,
                },
            })
        })
    })

    it("shows a permission state, not Not Found, when the intended parent is forbidden", () => {
        mockUseIntendedParent.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(403, "Forbidden", "Forbidden"),
            refetch: vi.fn(),
            isFetching: false,
        })

        render(<IntendedParentDetailPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Permission required" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Go to Dashboard" })).toHaveAttribute("href", "/dashboard")
        expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument()
        expect(screen.queryByText(/not found/i)).not.toBeInTheDocument()
        // History, activity and tasks wait for the record, so a denied record sends one request.
        expect(mockUseIntendedParentHistory).toHaveBeenLastCalledWith(null)
        expect(mockUseEntityActivity).toHaveBeenLastCalledWith("intended_parent", null)
        expect(mockUseTasks).toHaveBeenLastCalledWith(
            expect.objectContaining({ intended_parent_id: "ip1" }),
            { enabled: false },
        )
    })

    it("loads history, activity and tasks once the intended parent has loaded", () => {
        render(<IntendedParentDetailPage />)

        expect(mockUseIntendedParentHistory).toHaveBeenLastCalledWith("ip1")
        expect(mockUseEntityActivity).toHaveBeenLastCalledWith("intended_parent", "ip1")
        expect(mockUseTasks).toHaveBeenLastCalledWith(
            expect.objectContaining({ intended_parent_id: "ip1" }),
            { enabled: true },
        )
    })

    it("shows the not-found state for a missing intended parent", () => {
        mockUseIntendedParent.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(404, "Not Found", "Intended parent not found"),
            refetch: vi.fn(),
            isFetching: false,
        })

        render(<IntendedParentDetailPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Intended parent not found" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Intended Parents" })).toHaveAttribute("href", "/intended-parents")
    })

    it("offers a retry for other intended parent load failures", () => {
        const refetch = vi.fn()
        mockUseIntendedParent.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(500, "Server Error", "boom"),
            refetch,
            isFetching: false,
        })

        render(<IntendedParentDetailPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Couldn't load intended parent" })).toBeInTheDocument()
        expect(screen.queryByText("boom")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(refetch).toHaveBeenCalledOnce()
    })
})

describe('IntendedParentDetailPage stage changes', () => {
    beforeEach(() => {
        setUser('developer', DEFAULT_PERMISSIONS)
        mockUseIntendedParentStatuses.mockReturnValue({
            data: { statuses: IP_STAGE_STATUSES },
            isLoading: false,
            isError: false,
            isFetching: false,
            refetch: vi.fn(),
        })
        mockUpdateIntendedParentStatus.mockReset()
        mockUpdateIntendedParentStatus.mockResolvedValue({ status: 'applied' })
        mockUseIntendedParentHistory.mockReturnValue({ data: [] })
        mockUseIntendedParentNotes.mockReturnValue({ data: [] })
        mockUseTasks.mockReturnValue({ data: { items: [] } })
        mockUseIPAttachments.mockReturnValue({ data: [] })
        mockUseEntityActivity.mockReturnValue({
            data: { items: [], total: 0, page: 1, pages: 1 },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        setIntendedParentStage('stage-new', 'new', 'New')
    })

    function setIntendedParentStage(stageId: string, stageKey: string, label: string) {
        mockUseIntendedParent.mockReturnValue({
            data: {
                id: 'ip1',
                intended_parent_number: 'I10001',
                full_name: 'Bob Parent',
                email: 'bob@example.com',
                marital_status: null,
                status: stageKey,
                stage_id: stageId,
                stage_key: stageKey,
                stage_slug: stageKey,
                status_label: label,
                is_archived: false,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
            isLoading: false,
            error: null,
        })
    }

    function openChangeStage() {
        render(<IntendedParentDetailPage />)
        fireEvent.click(screen.getByRole('button', { name: 'Change Stage' }))
        return screen.getByTestId('change-stage-dialog')
    }

    it('prompts for a reason when the intended parent stage requires one', async () => {
        mockUseIntendedParentStatuses.mockReturnValue({
            data: {
                statuses: IP_STAGE_STATUSES.map((status) =>
                    status.id === 'stage-matched'
                        ? { ...status, semantics: { ...status.semantics, requires_reason_on_enter: true } }
                        : status,
                ),
            },
            isLoading: false,
            isError: false,
            isFetching: false,
            refetch: vi.fn(),
        })
        const dialog = openChangeStage()

        fireEvent.click(within(dialog).getByRole('button', { name: /matched/i }))

        expect(within(dialog).getByRole('button', { name: 'Save Change' })).toBeDisabled()
        fireEvent.change(within(dialog).getByLabelText(/reason/i), { target: { value: 'Contract signed' } })
        fireEvent.click(within(dialog).getByRole('button', { name: 'Save Change' }))

        await waitFor(() => {
            expect(mockUpdateIntendedParentStatus).toHaveBeenCalledWith({
                id: 'ip1',
                data: { stage_id: 'stage-matched', reason: 'Contract signed' },
            })
        })
    })

    it('does not apply surrogate on-hold behavior to an intended parent stage with the same key', async () => {
        mockUseIntendedParentStatuses.mockReturnValue({
            data: {
                statuses: [
                    ...IP_STAGE_STATUSES,
                    {
                        id: 'stage-on-hold',
                        value: 'on_hold',
                        label: 'Paused Search',
                        stage_key: 'on_hold',
                        stage_slug: 'on_hold',
                        stage_type: 'post_approval',
                        color: '#6B7280',
                        order: 4,
                        semantics: stageSemantics(),
                    },
                ],
            },
            isLoading: false,
            isError: false,
            isFetching: false,
            refetch: vi.fn(),
        })
        const dialog = openChangeStage()

        fireEvent.click(within(dialog).getByRole('button', { name: /paused search/i }))

        expect(within(dialog).queryByText('Follow-up reminder')).not.toBeInTheDocument()
        expect(within(dialog).queryByLabelText(/reason/i)).not.toBeInTheDocument()
        fireEvent.click(within(dialog).getByRole('button', { name: 'Save Change' }))
        await waitFor(() => {
            expect(mockUpdateIntendedParentStatus).toHaveBeenCalledWith({
                id: 'ip1',
                data: { stage_id: 'stage-on-hold' },
            })
        })
    })

    it.each([
        ['case_manager', ['change_intended_parent_status', 'approve_status_change_requests'], 'Save Change'],
        ['admin', ['change_intended_parent_status'], 'Request Approval'],
    ])('decides regression self-approval for %s from approve_status_change_requests', (role, permissions, action) => {
        setUser(role, permissions)
        setIntendedParentStage('stage-ready', 'ready_to_match', 'Ready to Match')
        const dialog = openChangeStage()

        fireEvent.click(within(dialog).getByRole('button', { name: /^new$/i }))

        expect(within(dialog).getByRole('button', { name: action })).toBeInTheDocument()
    })

    it('hides Change Stage without change_intended_parent_status', () => {
        setUser('case_manager', ['view_intended_parents', 'edit_intended_parents'])

        render(<IntendedParentDetailPage />)

        expect(screen.queryByRole('button', { name: 'Change Stage' })).not.toBeInTheDocument()
    })

    it('shows a loading state instead of built-in stages while stages load', () => {
        mockUseIntendedParentStatuses.mockReturnValue({
            data: undefined,
            isLoading: true,
            isError: false,
            isFetching: true,
            refetch: vi.fn(),
        })
        const dialog = openChangeStage()

        expect(within(dialog).getByRole('status')).toHaveTextContent('Loading stages')
        expect(within(dialog).queryByRole('button', { name: /ready to match/i })).not.toBeInTheDocument()
        expect(within(dialog).getByRole('button', { name: 'Save Change' })).toBeDisabled()
    })

    it('shows a retryable error instead of built-in stages when stages fail to load', () => {
        const refetch = vi.fn()
        mockUseIntendedParentStatuses.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            refetch,
        })
        const dialog = openChangeStage()

        expect(within(dialog).getByText("Couldn't load stages")).toBeInTheDocument()
        expect(within(dialog).queryByRole('button', { name: /ready to match/i })).not.toBeInTheDocument()
        expect(within(dialog).getByRole('button', { name: 'Save Change' })).toBeDisabled()
        fireEvent.click(within(dialog).getByRole('button', { name: 'Try again' }))
        expect(refetch).toHaveBeenCalledOnce()
    })
})

vi.mock("@/components/records/RecordAppointmentsCard", () => ({ RecordAppointmentsCard: () => null }))
vi.mock("@/components/records/RecordCorrespondenceCard", () => ({ RecordCorrespondenceCard: () => null }))
vi.mock("@/components/matches/RelatedMatchesCard", () => ({ RelatedMatchesCard: () => null }))
