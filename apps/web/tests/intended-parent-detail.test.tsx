import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import IntendedParentDetailPage from '../app/(app)/intended-parents/[id]/page'

const mockPush = vi.fn()
const mockUpdateIntendedParent = vi.fn()

vi.mock('next/link', () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock('next/navigation', () => ({
    useParams: () => ({ id: 'ip1' }),
    useRouter: () => ({ push: mockPush }),
}))

const mockUseIntendedParent = vi.fn()

vi.mock('@/lib/hooks/use-intended-parents', () => ({
    useIntendedParent: (id: string) => mockUseIntendedParent(id),
    useIntendedParentHistory: () => ({ data: [] }),
    useIntendedParentNotes: () => ({ data: [] }),
    useUpdateIntendedParent: () => ({ mutateAsync: mockUpdateIntendedParent, isPending: false }),
    useUpdateIntendedParentStatus: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useArchiveIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRestoreIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteIntendedParent: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCreateIntendedParentNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteIntendedParentNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('IntendedParentDetailPage', () => {
    beforeEach(() => {
        mockUpdateIntendedParent.mockReset()
        mockUpdateIntendedParent.mockResolvedValue({})
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
                partner_name: 'Pat Parent',
                partner_email: 'pat@example.com',
                partner_pronouns: 'They/Them',
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
                status: 'new',
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
                partner_name: 'Pat Parent',
                partner_email: 'pat@example.com',
                partner_pronouns: 'They/Them',
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
                status: 'new',
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
        fireEvent.click(screen.getByRole("menuitem", { name: /add section/i }))
        fireEvent.click(screen.getByRole("menuitem", { name: /ivf clinic/i }))

        expect(screen.getByRole("heading", { name: "IVF Clinic" })).toBeInTheDocument()
    })
})
