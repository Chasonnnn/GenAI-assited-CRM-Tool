import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within, waitFor } from "@testing-library/react"

import DonorDetailPage from "../app/(app)/donors/[id]/page"
import { donorProfileFixture } from "./fixtures/donor-profile"
import { ApiError } from "@/lib/api"

const mockUseDonorProfile = vi.fn()
const mockRevealDonor = vi.fn()
const mockUseDonor = vi.fn()
const mockUseDonorNotes = vi.fn()
const mockCreateDonorNote = vi.fn()
const mockDeleteDonorNote = vi.fn()
const mockUpdateDonor = vi.fn()
const mockUpdateDonorStatus = vi.fn()
const mockArchiveDonor = vi.fn()
const mockRestoreDonor = vi.fn()
const mockRouterPush = vi.fn()
const mockUseEffectivePermissions = vi.fn()
const mockUseTasks = vi.fn()
const mockCreateTask = vi.fn()
const mockUseDonorAttachments = vi.fn()
const mockUploadDonorAttachment = vi.fn()
const mockUploadDonorProfilePhoto = vi.fn()
const mockDownloadAttachment = vi.fn()
const mockDeleteDonorAttachment = vi.fn()
const mockUseAttachmentPreviewUrl = vi.fn()
const mockUseAuth = vi.fn()
const mockDetailSearchParams = new URLSearchParams()

vi.mock("@/components/rich-text-editor", () => ({
    RichTextEditor: ({ content, onChange, placeholder, ariaLabel }: { content: string; onChange: (html: string) => void; placeholder: string; ariaLabel: string }) => (
        <textarea aria-label={ariaLabel} placeholder={placeholder} value={content} onChange={(event) => onChange(event.target.value)} />
    ),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))

vi.mock("@/lib/hooks/use-entity-activity", () => ({
    useInfiniteEntityActivity: () => ({ data: { pages: [{ items: [] }] }, isLoading: false, isError: false, hasNextPage: false }),
    useEntityActivity: () => ({
        data: { items: [], total: 0, page: 1, pages: 1 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
    }),
}))

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "donor-1" }),
    useSearchParams: () => ({ get: (key: string) => mockDetailSearchParams.get(key) }),
    useRouter: () => ({ push: mockRouterPush }),
}))

vi.mock("next/link", () => ({
    default: ({ children, href, prefetch: _prefetch, ...props }: React.ComponentProps<"a"> & { prefetch?: boolean }) => (
        <a href={href} {...props}>{children}</a>
    ),
}))

vi.mock("@/components/ui/avatar", () => ({
    Avatar: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
    AvatarFallback: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
    AvatarImage: ({ src, alt }: { src: string; alt: string }) => (
        <span role="img" aria-label={alt} data-src={src} />
    ),
}))

vi.mock("@/lib/hooks/use-donors", () => ({
    useDonorProfile: () => mockUseDonorProfile(),
    useRevealDonorSensitiveInfo: () => ({ mutateAsync: mockRevealDonor, isPending: false, reset: vi.fn() }),
    useDonorOwnerOptions: () => ({ data: { users: [], queues: [] }, isLoading: false, isError: false }),
    useDonor: (id: string) => mockUseDonor(id),
    useDonorNotes: () => mockUseDonorNotes(),
    useDonorHistory: () => ({
        data: [
            {
                id: "history-1",
                donor_id: "donor-1",
                changed_by_user_id: "user-1",
                old_stage_id: "egg-new",
                new_stage_id: "egg-ready",
                old_status: "new",
                new_status: "ready_to_match",
                old_label_snapshot: "New",
                new_label_snapshot: "Ready to Match",
                reason: "Screening completed",
                effective_at: "2026-08-28T12:00:00Z",
                recorded_at: "2026-08-28T12:00:00Z",
            },
        ],
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
    }),
    useClaimDonor: () => ({mutateAsync: vi.fn(), isPending: false}),
    useUpdateDonor: () => ({ mutateAsync: mockUpdateDonor, isPending: false }),
    useUpdateDonorStatus: () => ({ mutateAsync: mockUpdateDonorStatus, isPending: false }),
    useArchiveDonor: () => ({ mutateAsync: mockArchiveDonor, isPending: false }),
    useRestoreDonor: () => ({ mutateAsync: mockRestoreDonor, isPending: false }),
    useCreateDonorNote: () => ({ mutateAsync: mockCreateDonorNote, isPending: false }),
    useDeleteDonorNote: () => ({ mutateAsync: mockDeleteDonorNote, isPending: false }),
}))

vi.mock("@/lib/hooks/use-pipelines", () => ({
    useDefaultPipeline: () => ({
        data: {
            stages: [
                {
                    id: "egg-new",
                    stage_key: "new",
                    slug: "new",
                    label: "New",
                    color: "#3B82F6",
                    order: 1,
                    stage_type: "intake",
                    is_active: true,
                },
                {
                    id: "egg-ready",
                    stage_key: "ready_to_match",
                    slug: "ready-to-match",
                    label: "Ready to Match",
                    color: "#F59E0B",
                    order: 2,
                    stage_type: "post_approval",
                    is_active: true,
                },
                {
                    id: "egg-on-hold",
                    stage_key: "on_hold",
                    slug: "on-hold",
                    label: "On-Hold",
                    color: "#B4536A",
                    order: 3,
                    stage_type: "paused",
                    is_active: true,
                    semantics: {
                        requires_reason_on_enter: true,
                    },
                },
            ],
        },
    }),
}))

vi.mock("@/lib/hooks/use-tasks", () => ({
    useTasks: (params: unknown, options: unknown) => mockUseTasks(params, options),
    useCreateTask: () => ({ mutateAsync: mockCreateTask, isPending: false }),
    useCreateTaskBatch: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateTask: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCompleteTask: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUncompleteTask: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteTask: () => ({ mutateAsync: vi.fn(), isPending: false }),

}))

vi.mock("@/lib/hooks/use-attachments", () => ({
    useDonorAttachments: () => mockUseDonorAttachments(),
    useUploadDonorAttachment: () => ({ mutateAsync: mockUploadDonorAttachment, isPending: false }),
    useUploadDonorProfilePhoto: () => ({ mutateAsync: mockUploadDonorProfilePhoto, isPending: false }),
    useDownloadAttachment: () => ({ mutate: mockDownloadAttachment, isPending: false }),
    useDeleteDonorAttachment: () => ({ mutateAsync: mockDeleteDonorAttachment, isPending: false }),
    useAttachmentPreviewUrl: () => mockUseAttachmentPreviewUrl(),
}))

describe("DonorDetailPage", () => {
    beforeEach(() => {
        mockDetailSearchParams.delete("return_to")
        mockUseAuth.mockReset()
        mockUseAuth.mockReturnValue({ user: { user_id: "user-1", role: "admin" } })
        mockDetailSearchParams.delete("tab")
        mockUseDonorProfile.mockReset().mockReturnValue({ data: donorProfileFixture, isPending: false, isError: false, refetch: vi.fn() })
        mockRevealDonor.mockReset().mockResolvedValue({ ssn: null, partner_ssn: null })
        mockUseDonor.mockReset()
        mockUseDonorNotes.mockReset()
        mockUseDonorNotes.mockReturnValue({
            data: [{
                id: "note-1",
                author_id: "user-1",
                content: "<p>Screening call complete</p>",
                created_at: "2026-08-29T12:00:00Z",
            }],
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        mockCreateDonorNote.mockReset().mockResolvedValue({})
        mockDeleteDonorNote.mockReset().mockResolvedValue(undefined)
        mockUpdateDonor.mockReset()
        mockUpdateDonor.mockResolvedValue({})
        mockUpdateDonorStatus.mockReset()
        mockUpdateDonorStatus.mockResolvedValue({
            status: "applied",
            donor: null,
            history: null,
            request_id: null,
            message: null,
        })
        mockArchiveDonor.mockReset()
        mockArchiveDonor.mockResolvedValue({})
        mockRestoreDonor.mockReset()
        mockRestoreDonor.mockResolvedValue({})
        mockRouterPush.mockReset()
        mockUseEffectivePermissions.mockReset()
        mockUseEffectivePermissions.mockReturnValue({
            data: {
                permissions: [
                    "view_donors",
                    "edit_donors",
                    "archive_donors",
                    "change_donor_status",
                    "view_tasks",
                    "create_tasks",
                ],
            },
        })
        mockCreateTask.mockReset()
        mockCreateTask.mockResolvedValue({})
        mockUseTasks.mockReset()
        mockUseTasks.mockReturnValue({
            data: {
                items: [{
                    id: "task-1",
                    title: "Review profile photo",
                    description: null,
                    task_type: "review",
                    surrogate_id: null,
                    intended_parent_id: null,
                    donor_id: "donor-1",
                    surrogate_number: null,
                    donor_number: "D10001",
                    donor_type: "egg",
                    donor_name: "Maya Thompson",
                    owner_type: "user",
                    owner_id: "user-1",
                    owner_name: "Owner",
                    created_by_user_id: "user-1",
                    created_by_name: "Owner",
                    due_date: "2026-09-01",
                    due_time: null,
                    duration_minutes: null,
                    is_completed: false,
                    completed_at: null,
                    completed_by_name: null,
                    created_at: "2026-08-29T12:00:00Z",
                }],
            },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        mockUploadDonorAttachment.mockReset().mockResolvedValue({})
        mockUploadDonorProfilePhoto.mockReset().mockResolvedValue({})
        mockDownloadAttachment.mockReset()
        mockDeleteDonorAttachment.mockReset().mockResolvedValue(undefined)
        mockUseAttachmentPreviewUrl.mockReset()
        mockUseAttachmentPreviewUrl.mockReturnValue({ data: undefined, isLoading: false })
        mockUseDonorAttachments.mockReset()
        mockUseDonorAttachments.mockReturnValue({
            data: [{
                id: "attachment-1",
                filename: "screening.pdf",
                content_type: "application/pdf",
                file_size: 2048,
                scan_status: "clean",
                quarantined: false,
                uploaded_by_user_id: "user-1",
                created_at: "2026-08-29T12:00:00Z",
            }],
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        mockUseDonor.mockReturnValue({
            data: {
                id: "donor-1",
                donor_number: "D10001",
                donor_type: "egg",
                full_name: "Maya Thompson",
                email: "maya@example.com",
                phone: "(415) 555-0142",
                state: "CA",
                education: "B.S. Biology",
                source: "manual",
                owner_type: null,
                owner_id: null,
                stage_id: "egg-ready",
                stage_key: "ready_to_match",
                stage_slug: "ready-to-match",
                status: "ready_to_match",
                status_label: "Ready to Match",
                profile_photo_attachment_id: null,
                is_archived: false,
                archived_at: null,
                created_at: "2026-08-27T12:00:00Z",
                updated_at: "2026-08-27T12:00:00Z",
            },
            isLoading: false,
            isError: false,
            error: null,
            refetch: vi.fn(),
        })
    })

    it("keeps collaborator management out of the record overview under v2", () => {
        mockUseEffectivePermissions.mockReturnValue({ data: {
            policy_version: 2,
            role: "admin",
            permissions: ["view_donors", "edit_donors", "assign_donors"],
        } })
        render(<DonorDetailPage />)

        expect(screen.getByRole("heading", { name: "Owner" })).toBeInTheDocument()
        expect(screen.queryByText("Intake collaborators")).not.toBeInTheDocument()
        expect(screen.queryByRole("combobox", { name: "Intake specialist" })).not.toBeInTheDocument()
    })

    it("uses the compact entity header and action hierarchy shared by other detail pages", async () => {
        render(<DonorDetailPage />)

        const header = screen.getByRole("banner")
        expect(header).toHaveClass("min-h-16", "border-b")
        expect(within(header).getByRole("button", { name: "Back" })).toBeInTheDocument()
        expect(within(header).getByRole("heading", { name: "Donor #D10001" })).toBeInTheDocument()
        expect(within(header).getByRole("button", { name: "Change Stage" })).toBeInTheDocument()

        fireEvent.click(within(header).getByRole("button", { name: "Actions for Maya Thompson" }))
        expect(await screen.findByRole("menuitem", { name: "Edit" })).toBeInTheDocument()
        expect(screen.getByRole("menuitem", { name: "Archive" })).toBeInTheDocument()
    })

    it("uses the surrogate overview cards and keeps notes, tasks and attachments in their tabs", () => {
        render(<DonorDetailPage />)
        expect(screen.getAllByRole("tab").map(tab => tab.textContent)).toEqual(["Overview", "Notes", "Tasks", "History"])
        const overview = screen.getByRole("tabpanel", { name: "Overview" })
        for (const title of ["Contact Information", "Demographics", "Personal Information", "Medical & Insurance", "Activity", "Eligibility Checklist", "Owner"]) {
            expect(within(overview).getByText(title)).toBeInTheDocument()
        }
        for (const title of ["Appointments", "Propose Match", "Documents"]) {
            expect(within(overview).queryByText(title)).not.toBeInTheDocument()
        }
        expect(screen.getByText("Maya Thompson")).toBeInTheDocument()
        expect(screen.getByText("maya@example.com")).toBeInTheDocument()
        expect(screen.getByText("21.8")).toBeInTheDocument()
        expect(screen.getByText("Screening completed")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("tab", { name: "Notes" }))
        expect(screen.getByRole("heading", { name: "Attachments" })).toBeInTheDocument()
        expect(screen.getByText("screening.pdf")).toBeInTheDocument()
        expect(screen.getByText("Screening call complete")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("tab", { name: "Tasks" }))
        expect(screen.getByRole("button", { name: "List" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Calendar" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /Review profile photo/ })).toBeInTheDocument()
        expect(mockUseTasks).toHaveBeenCalledWith(expect.objectContaining({ donor_id: "donor-1", per_page: 100 }), { enabled: true })
    })

    it("adds and deletes donor notes", async () => {
        mockDetailSearchParams.set("tab", "notes")
        render(<DonorDetailPage />)

        fireEvent.change(screen.getByPlaceholderText("Add a note..."), {
            target: { value: "  Follow up next week  " },
        })
        fireEvent.click(screen.getByRole("button", { name: "Add Note" }))

        await waitFor(() => expect(mockCreateDonorNote).toHaveBeenCalledWith({
            donorId: "donor-1",
            data: { content: "Follow up next week" },
        }))
        await waitFor(() => {
            expect(screen.getByPlaceholderText("Add a note...")).toHaveValue("")
        })

        fireEvent.click(screen.getByRole("button", { name: /Delete note by/ }))
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete Note" }))
        await waitFor(() => expect(mockDeleteDonorNote).toHaveBeenCalledWith({
            donorId: "donor-1",
            noteId: "note-1",
        }))
    })

    it("renders donor note loading, error/retry, and empty states", () => {
        mockDetailSearchParams.set("tab", "notes")
        mockUseDonorNotes.mockReturnValueOnce({
            data: undefined,
            isLoading: true,
            isError: false,
            refetch: vi.fn(),
        })
        const first = render(<DonorDetailPage />)
        expect(screen.getByText("Loading notes…")).toBeInTheDocument()
        first.unmount()

        const refetch = vi.fn()
        mockUseDonorNotes.mockReturnValueOnce({
            data: undefined,
            isLoading: false,
            isError: true,
            refetch,
        })
        const second = render(<DonorDetailPage />)
        expect(screen.getByText("Failed to load notes.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry notes" }))
        expect(refetch).toHaveBeenCalledTimes(1)
        second.unmount()

        mockUseDonorNotes.mockReturnValueOnce({
            data: [],
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        render(<DonorDetailPage />)
        expect(screen.getByText("No notes yet.")).toBeInTheDocument()
    })

    it("limits donor note controls by edit permission and note ownership", () => {
        mockDetailSearchParams.set("tab", "notes")
        mockUseEffectivePermissions.mockReturnValueOnce({
            data: { permissions: ["view_donors"] },
        })
        const first = render(<DonorDetailPage />)
        expect(screen.queryByPlaceholderText("Add a note...")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Delete note by/ })).not.toBeInTheDocument()
        first.unmount()

        mockUseAuth.mockReturnValueOnce({ user: { user_id: "user-2", role: "case_manager" } })
        mockUseEffectivePermissions.mockReturnValueOnce({
            data: { permissions: ["view_donors", "edit_donors"] },
        })
        render(<DonorDetailPage />)
        expect(screen.getByPlaceholderText("Add a note...")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Delete note by/ })).not.toBeInTheDocument()
    })

    it.each([
        { donorType: "egg", photoId: null },
        { donorType: "egg", photoId: "profile-1" },
        { donorType: "sperm", photoId: null },
        { donorType: "sperm", photoId: "profile-1" },
    ])("omits header photo controls for $donorType donors with photo $photoId", ({ donorType, photoId }) => {
        mockUseDonor.mockReturnValue({
            ...mockUseDonor(),
            data: {
                ...mockUseDonor().data,
                donor_type: donorType,
                profile_photo_attachment_id: photoId,
            },
        })
        mockUseAttachmentPreviewUrl.mockReturnValue({
            data: { download_url: "https://files.example/profile.jpg", filename: "profile.jpg" },
            isLoading: false,
        })
        render(<DonorDetailPage />)

        const header = within(screen.getByRole("banner"))
        expect(header.queryByRole("img", { name: "Maya Thompson profile photo" })).not.toBeInTheDocument()
        expect(header.queryByRole("button", { name: /donor profile photo/i })).not.toBeInTheDocument()
        expect(header.queryByLabelText(/Choose .*donor profile photo/i)).not.toBeInTheDocument()
        expect(header.getByRole("button", { name: "Change Stage" })).toBeInTheDocument()
        expect(mockUseAttachmentPreviewUrl).not.toHaveBeenCalled()
        expect(mockUploadDonorProfilePhoto).not.toHaveBeenCalled()
    })

    it("renders donor document loading, error/retry, and empty states", () => {
        mockDetailSearchParams.set("tab", "notes")
        mockUseDonorAttachments.mockReturnValueOnce({
            data: undefined,
            isLoading: true,
            isError: false,
            refetch: vi.fn(),
        })
        const first = render(<DonorDetailPage />)
        expect(screen.getByText("Loading documents…")).toBeInTheDocument()
        first.unmount()

        const refetch = vi.fn()
        mockUseDonorAttachments.mockReturnValueOnce({
            data: undefined,
            isLoading: false,
            isError: true,
            refetch,
        })
        const second = render(<DonorDetailPage />)
        expect(screen.getByText("Failed to load documents.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(refetch).toHaveBeenCalledTimes(1)
        second.unmount()

        mockUseDonorAttachments.mockReturnValueOnce({
            data: [],
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        render(<DonorDetailPage />)
        expect(screen.getByText("No documents yet")).toBeInTheDocument()
    })

    it("downloads and deletes donor documents", async () => {
        mockDetailSearchParams.set("tab", "notes")
        render(<DonorDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Download screening.pdf" }))
        expect(mockDownloadAttachment).toHaveBeenCalledWith("attachment-1")
        fireEvent.click(screen.getByRole("button", { name: "Delete screening.pdf" }))
        fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Delete" }))

        await waitFor(() => expect(mockDeleteDonorAttachment).toHaveBeenCalledWith({
            donorId: "donor-1",
            attachmentId: "attachment-1",
        }))
    })

    it("edits donor basic details without exposing donor type as mutable", async () => {
        render(<DonorDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Actions for Maya Thompson" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Edit" }))
        expect(screen.queryByLabelText("Donor type")).not.toBeInTheDocument()
        expect(screen.getByLabelText("Email")).toHaveValue("maya@example.com")
        expect(screen.getByLabelText("Phone")).toHaveValue("(415) 555-0142")
        fireEvent.change(screen.getByLabelText("Education"), {
            target: { value: "M.S. Biology" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save Changes" }))

        await waitFor(() => {
            expect(mockUpdateDonor).toHaveBeenCalledWith({
                id: "donor-1",
                data: expect.objectContaining({
                    full_name: "Maya Thompson",
                    email: "maya@example.com",
                    phone: "(415) 555-0142",
                    education: "M.S. Biology",
                }),
            })
        })
        expect(mockUpdateDonor.mock.calls[0]?.[0]?.data).not.toHaveProperty("donor_type")
        expect(mockUpdateDonor.mock.calls[0]?.[0]?.data).not.toHaveProperty("stage_id")
    })

    it("changes stage using the donor type's pipeline stage id", async () => {
        render(<DonorDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Change Stage" }))
        fireEvent.click(screen.getByRole("button", { name: /^New$/ }))
        fireEvent.change(screen.getByLabelText(/Reason/), {
            target: { value: "Correcting the donor stage" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save Change" }))

        await waitFor(() => {
            expect(mockUpdateDonorStatus).toHaveBeenCalledWith({
                id: "donor-1",
                data: {
                    stage_id: "egg-new",
                    reason: "Correcting the donor stage",
                },
            })
        })
    })

    it("requires and submits a reason for a donor stage configured to require one", async () => {
        render(<DonorDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Change Stage" }))
        fireEvent.click(screen.getByRole("button", { name: "On-Hold" }))

        const saveButton = screen.getByRole("button", { name: "Save Change" })
        expect(saveButton).toBeDisabled()
        fireEvent.change(screen.getByLabelText(/Reason/), {
            target: { value: "Waiting on availability" },
        })
        expect(saveButton).toBeEnabled()
        fireEvent.click(saveButton)

        await waitFor(() => {
            expect(mockUpdateDonorStatus).toHaveBeenCalledWith({
                id: "donor-1",
                data: {
                    stage_id: "egg-on-hold",
                    reason: "Waiting on availability",
                },
            })
        })
    })

    it("uses the shared approval flow for a non-admin donor regression", async () => {
        mockUseAuth.mockReturnValue({ user: { user_id: "user-1", role: "case_manager" } })
        mockUpdateDonorStatus.mockResolvedValueOnce({
            status: "pending_approval",
            donor: null,
            history: null,
            request_id: "request-1",
            message: "Regression requires admin approval. Request submitted.",
        })
        render(<DonorDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Change Stage" }))
        expect(screen.getByText("Current: Ready to Match")).toBeInTheDocument()
        expect(screen.getByRole("switch", { name: "Effective now" })).toBeChecked()
        fireEvent.click(screen.getByRole("button", { name: /^New$/ }))

        expect(screen.getByText("Admin Approval Required")).toBeInTheDocument()
        const submit = screen.getByRole("button", { name: "Request Approval" })
        expect(submit).toBeDisabled()
        fireEvent.change(screen.getByLabelText(/Reason/), {
            target: { value: "Correcting screening stage" },
        })
        fireEvent.click(submit)

        await waitFor(() => {
            expect(mockUpdateDonorStatus).toHaveBeenCalledWith({
                id: "donor-1",
                data: {
                    stage_id: "egg-new",
                    reason: "Correcting screening stage",
                },
            })
        })
    })

    it("archives a donor after confirmation and returns to the list", async () => {
        mockDetailSearchParams.set(
            "return_to",
            "/donors?type=sperm&stage=sperm-ready&q=maya&page=2",
        )
        vi.spyOn(window, "confirm").mockReturnValueOnce(true)
        render(<DonorDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Back" }))
        expect(mockRouterPush).toHaveBeenCalledWith("/donors?type=sperm&stage=sperm-ready&q=maya&page=2")
        expect(screen.getByRole("link", { name: "View full history →" })).toHaveAttribute(
            "href",
            "/donors/donor-1?tab=history&return_to=%2Fdonors%3Ftype%3Dsperm%26stage%3Dsperm-ready%26q%3Dmaya%26page%3D2",
        )

        fireEvent.click(screen.getByRole("button", { name: "Actions for Maya Thompson" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Archive" }))

        await waitFor(() => expect(mockArchiveDonor).toHaveBeenCalledWith("donor-1"))
        expect(mockRouterPush).toHaveBeenCalledWith(
            "/donors?type=sperm&stage=sperm-ready&q=maya&page=2",
        )
    })

    it("restores an archived donor", async () => {
        const current = mockUseDonor().data
        mockUseDonor.mockReturnValue({
            data: { ...current, is_archived: true, archived_at: "2026-08-29T12:00:00Z" },
            isLoading: false,
            isError: false,
            error: null,
            refetch: vi.fn(),
        })
        render(<DonorDetailPage />)

        expect(screen.queryByRole("button", { name: "Edit Donor" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Change Stage" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Add Task" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Upload donor profile photo" })).not.toBeInTheDocument()
        expect(screen.getAllByText("Review profile photo").length).toBeGreaterThanOrEqual(1)
        fireEvent.click(screen.getByRole("button", { name: "Actions for Maya Thompson" }))
        expect(screen.queryByRole("menuitem", { name: "Edit" })).not.toBeInTheDocument()
        fireEvent.click(await screen.findByRole("menuitem", { name: "Restore" }))

        await waitFor(() => expect(mockRestoreDonor).toHaveBeenCalledWith("donor-1"))
    })

    it("distinguishes not found from permission and retryable errors", () => {
        mockDetailSearchParams.set("return_to", "/donors?type=sperm&page=3")
        mockUseDonor.mockReturnValueOnce({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(404, "Not Found", "Not Found"),
            refetch: vi.fn(),
        })
        const { unmount } = render(<DonorDetailPage />)
        expect(screen.getByRole("heading", { name: "Donor not found" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to donors" })).toHaveAttribute(
            "href",
            "/donors?type=sperm&page=3",
        )
        unmount()

        mockUseDonor.mockReturnValueOnce({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(403, "Forbidden", "Forbidden"),
            refetch: vi.fn(),
        })
        render(<DonorDetailPage />)
        expect(screen.getByText("Permission required")).toBeInTheDocument()
    })

    it("rejects external and non-list return targets", () => {
        mockDetailSearchParams.set("return_to", "//evil.example/steal")
        render(<DonorDetailPage />)
        fireEvent.click(screen.getByRole("button", { name: "Back" }))
        expect(mockRouterPush).toHaveBeenCalledWith("/donors")
    })

    it("renders profile loading and retry states without displaying blank saved fields", () => {
        mockUseDonorProfile.mockReturnValueOnce({ isPending: true, isError: false })
        const first = render(<DonorDetailPage />)
        expect(screen.getByRole("status")).toHaveTextContent("Loading donor information")
        expect(screen.queryByText("Demographics")).not.toBeInTheDocument()
        first.unmount()
        const refetch = vi.fn()
        mockUseDonorProfile.mockReturnValueOnce({ isPending: false, isError: true, refetch })
        render(<DonorDetailPage />)
        expect(screen.getByRole("alert")).toHaveTextContent("Unable to load donor information")
        fireEvent.click(screen.getByRole("button", { name: "Retry donor information" }))
        expect(refetch).toHaveBeenCalledTimes(1)
    })

    it("disables profile edits for readers and archived records", () => {
        mockUseEffectivePermissions.mockReturnValue({ data: { permissions: ["view_donors"] } })
        render(<DonorDetailPage />)
        expect(screen.queryByRole("button", { name: "Edit Full name" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Edit Personal Information" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Edit Info" })).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Nicotine / tobacco use: Not answered." })).toBeDisabled()
    })

    it("retries a failed detail request", () => {
        const refetch = vi.fn()
        mockUseDonor.mockReturnValueOnce({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new Error("Network failure"),
            refetch,
        })

        render(<DonorDetailPage />)
        expect(screen.getByRole("heading", { name: "Failed to load donor" })).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(refetch).toHaveBeenCalledTimes(1)
    })

    it("shows only donor actions allowed by effective permissions", async () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_donors", "edit_donors"] },
        })

        render(<DonorDetailPage />)
        fireEvent.click(screen.getByRole("button", { name: "Actions for Maya Thompson" }))
        expect(await screen.findByRole("menuitem", { name: "Edit" })).toBeInTheDocument()
        expect(screen.queryByRole("menuitem", { name: "Archive" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Change Stage" })).not.toBeInTheDocument()
        expect(screen.queryByRole("heading", { name: "Tasks" })).not.toBeInTheDocument()
    })

    it("keeps donor attachment mutations behind edit permission", () => {
        mockDetailSearchParams.set("tab", "notes")
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_donors"] },
        })

        render(<DonorDetailPage />)
        expect(screen.queryByLabelText("Upload donor documents")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Delete screening.pdf" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Upload donor profile photo" })).not.toBeInTheDocument()
    })
})

vi.mock("@/components/records/RecordAppointmentsCard", () => ({ RecordAppointmentsCard: () => null }))
vi.mock("@/components/records/RecordCorrespondenceCard", () => ({ RecordCorrespondenceCard: () => null }))
vi.mock("@/components/matches/RelatedMatchesCard", () => ({ RelatedMatchesCard: () => null }))
