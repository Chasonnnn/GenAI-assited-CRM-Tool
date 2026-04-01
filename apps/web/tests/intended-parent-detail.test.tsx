import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import IntendedParentDetailPage from '../app/(app)/intended-parents/[id]/page'

const mockPush = vi.fn()
const mockUpdateIntendedParent = vi.fn()
const mockUseIntendedParentHistory = vi.fn()
const mockUseIntendedParentNotes = vi.fn()
const mockUseTasks = vi.fn()
const mockUseIPAttachments = vi.fn()

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
    useAuth: () => ({
        user: { role: 'developer', user_id: 'user-1' },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
    }),
}))

const mockUseIntendedParent = vi.fn()

vi.mock('@/lib/hooks/use-intended-parents', () => ({
    useIntendedParent: (id: string) => mockUseIntendedParent(id),
    useIntendedParentHistory: () => mockUseIntendedParentHistory(),
    useIntendedParentNotes: () => mockUseIntendedParentNotes(),
    useUpdateIntendedParent: () => ({ mutateAsync: mockUpdateIntendedParent, isPending: false }),
    useUpdateIntendedParentStatus: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useArchiveIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRestoreIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCreateIntendedParentNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteIntendedParentNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/lib/hooks/use-metadata', () => ({
    useIntendedParentStatuses: () => ({
        data: {
            statuses: [
                {
                    id: 'stage-new',
                    value: 'new',
                    label: 'New',
                    stage_key: 'new',
                    stage_slug: 'new',
                    stage_type: 'intake',
                    color: '#3B82F6',
                    order: 1,
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
                },
            ],
        },
    }),
}))

vi.mock('@/lib/hooks/use-tasks', () => ({
    useTasks: (...args: unknown[]) => mockUseTasks(...args),
}))

vi.mock('@/lib/hooks/use-attachments', () => ({
    useIPAttachments: (...args: unknown[]) => mockUseIPAttachments(...args),
}))

describe('IntendedParentDetailPage', () => {
    beforeEach(() => {
        mockUpdateIntendedParent.mockReset()
        mockUpdateIntendedParent.mockResolvedValue({})
        mockUseIntendedParentHistory.mockReturnValue({ data: [] })
        mockUseIntendedParentNotes.mockReturnValue({ data: [] })
        mockUseTasks.mockReturnValue({ data: { items: [] } })
        mockUseIPAttachments.mockReturnValue({ data: [] })
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

    it('renders primary details', () => {
        render(<IntendedParentDetailPage />)
        expect(screen.getByText('Bob Parent')).toBeInTheDocument()
        expect(screen.getAllByText('bob@example.com').length).toBeGreaterThan(0)
    })

    it("adds accessible labels to the back link and actions menu", () => {
        render(<IntendedParentDetailPage />)

        expect(screen.getByRole("link", { name: "Back to intended parents" })).toBeInTheDocument()
        expect(
            screen.getByRole("button", { name: "Actions for Bob Parent" })
        ).toBeInTheDocument()
    })

    it("moves Change Stage into the header and removes old status terminology from the detail page", () => {
        render(<IntendedParentDetailPage />)

        expect(screen.getByRole("button", { name: "Change Stage" })).toBeInTheDocument()
        expect(screen.queryByRole("heading", { name: "Status" })).not.toBeInTheDocument()
        expect(screen.getByText("Activity")).toBeInTheDocument()
        expect(screen.queryByText("Stage History")).not.toBeInTheDocument()
        expect(screen.queryByText("Created:")).not.toBeInTheDocument()
        expect(screen.queryByText("Last Activity:")).not.toBeInTheDocument()
    })

    it("renders intended-parent activity in the same staged journey format as surrogate details", () => {
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
        mockUseIPAttachments.mockReturnValueOnce({
            data: [
                {
                    id: "attachment-1",
                    filename: "Legal packet.pdf",
                    content_type: "application/pdf",
                    file_size: 2048,
                    scan_status: "clean",
                    quarantined: false,
                    uploaded_by_user_id: "user-1",
                    created_at: "2026-02-26T21:46:00Z",
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

    it("renders marital status and per-person DOB on detail cards", () => {
        render(<IntendedParentDetailPage />)

        expect(screen.getByText("Marital Status")).toBeInTheDocument()
        expect(screen.getByText("Married")).toBeInTheDocument()
        expect(screen.getByText("May 15, 1989")).toBeInTheDocument()
        expect(screen.getByText("Aug 9, 1991")).toBeInTheDocument()
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
        fireEvent.click(screen.getByRole("button", { name: "Edit Clinic/Hospital name" }))
        fireEvent.change(screen.getByLabelText("Clinic/Hospital name"), {
            target: { value: "CCRM Austin" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save Clinic/Hospital name" }))

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

    it("shows friendly labels for embryo source values", () => {
        render(<IntendedParentDetailPage />)

        expect(screen.getByRole("heading", { name: "Embryo Status" })).toBeInTheDocument()
        expect(screen.getByText("Intended Mother")).toBeInTheDocument()
        expect(screen.getByText("Sperm Donor")).toBeInTheDocument()
        expect(screen.getByText("Yes")).toBeInTheDocument()
    })

    it("lays out medical subsections in the same two-column grid pattern as surrogate details", () => {
        render(<IntendedParentDetailPage />)

        expect(screen.getByTestId("ip-medical-sections-grid")).toHaveClass("grid", "gap-4", "md:grid-cols-2")
    })
})
