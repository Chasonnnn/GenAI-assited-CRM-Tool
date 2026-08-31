import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"

import DonorDetailPage from "../app/(app)/donors/[id]/page"
import { ApiError } from "@/lib/api"

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

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))

vi.mock("@/lib/hooks/use-entity-activity", () => ({
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

    it("uses the compact entity header and action hierarchy shared by other detail pages", async () => {
        render(<DonorDetailPage />)

        const header = screen.getByRole("banner")
        const layout = header.firstElementChild
        expect(layout).toHaveClass("flex-col", "sm:flex-row")
        expect(within(header).getByRole("link", { name: "Back to donors" })).toBeInTheDocument()
        expect(within(header).getByRole("heading", { name: "Maya Thompson" })).toBeInTheDocument()
        expect(
            within(header).getByText("D10001 • Egg Donor • maya@example.com"),
        ).toBeInTheDocument()
        const changeStage = within(header).getByRole("button", { name: "Change Stage" })
        expect(changeStage).toBeInTheDocument()
        expect(changeStage.parentElement).toHaveClass("w-full", "sm:w-auto")

        fireEvent.click(within(header).getByRole("button", { name: "Actions for Maya Thompson" }))
        expect(await screen.findByRole("menuitem", { name: "Edit" })).toBeInTheDocument()
        expect(screen.getByRole("menuitem", { name: "Archive" })).toBeInTheDocument()
    })

    it("uses a primary detail column with stage activity in the side column", () => {
        render(<DonorDetailPage />)

        const details = screen.getByRole("region", { name: "Donor details" })
        expect(within(details).getByText("Contact Information")).toBeInTheDocument()
        expect(within(details).getByText("Donor Information")).toBeInTheDocument()
        expect(within(details).getByText("Created")).toBeInTheDocument()
        expect(within(details).queryByText("Egg Donor")).not.toBeInTheDocument()
        expect(within(details).getByRole("heading", { name: "Notes" })).toBeInTheDocument()
        expect(within(details).getByRole("heading", { name: "Documents" })).toBeInTheDocument()
        expect(within(details).getByRole("heading", { name: "Open Tasks" })).toBeInTheDocument()

        const activity = screen.getByRole("complementary", { name: "Donor activity" })
        expect(within(activity).getByRole("heading", { name: "Activity" })).toBeInTheDocument()
        expect(within(activity).getByText("Screening completed")).toBeInTheDocument()
        expect(screen.queryByRole("heading", { name: "Stage History" })).not.toBeInTheDocument()
    })

    it("renders donor identity and basic profile details", () => {
        const { container } = render(<DonorDetailPage />)

        expect(screen.getByRole("link", { name: "Back to donors" })).toHaveAttribute(
            "href",
            "/donors",
        )
        expect(screen.getByRole("heading", { name: "Maya Thompson" })).toBeInTheDocument()
        expect(screen.getByText("D10001 • Egg Donor • maya@example.com")).toBeInTheDocument()
        expect(screen.getByText("B.S. Biology")).toBeInTheDocument()
        expect(screen.getAllByText("Ready to Match").length).toBeGreaterThan(0)
        expect(screen.getByRole("heading", { name: "Activity" })).toBeInTheDocument()
        expect(screen.getByText("Screening completed")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Change Stage" })).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "Open Tasks" })).toBeInTheDocument()
        expect(screen.getAllByText("Review profile photo").length).toBeGreaterThanOrEqual(1)
        expect(screen.getByRole("link", { name: "Egg Donor D10001" })).toHaveAttribute(
            "href",
            "/donors/donor-1",
        )
        expect(mockUseTasks).toHaveBeenCalledWith(
            expect.objectContaining({ donor_id: "donor-1", is_completed: false, per_page: 10 }),
            { enabled: true },
        )
        expect(screen.getByRole("heading", { name: "Documents" })).toBeInTheDocument()
        expect(screen.getByText("screening.pdf")).toBeInTheDocument()
        expect(screen.getByLabelText("Upload donor documents")).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "Notes" })).toBeInTheDocument()
        expect(screen.getByText("Screening call complete")).toBeInTheDocument()
        expect(container.querySelector("main")).not.toBeInTheDocument()
    })

    it("adds and deletes donor notes", async () => {
        vi.spyOn(window, "confirm").mockReturnValueOnce(true)
        render(<DonorDetailPage />)

        fireEvent.change(screen.getByPlaceholderText("Add a note..."), {
            target: { value: "  Follow up next week  " },
        })
        fireEvent.click(screen.getByRole("button", { name: "Add Note" }))

        await vi.waitFor(() => expect(mockCreateDonorNote).toHaveBeenCalledWith({
            donorId: "donor-1",
            data: { content: "Follow up next week" },
        }))
        await vi.waitFor(() => {
            expect(screen.getByPlaceholderText("Add a note...")).toHaveValue("")
        })

        fireEvent.click(screen.getByRole("button", { name: /Delete note from/ }))
        await vi.waitFor(() => expect(mockDeleteDonorNote).toHaveBeenCalledWith({
            donorId: "donor-1",
            noteId: "note-1",
        }))
    })

    it("renders donor note loading, error/retry, and empty states", () => {
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
        mockUseEffectivePermissions.mockReturnValueOnce({
            data: { permissions: ["view_donors"] },
        })
        const first = render(<DonorDetailPage />)
        expect(screen.queryByPlaceholderText("Add a note...")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Delete note from/ })).not.toBeInTheDocument()
        first.unmount()

        mockUseAuth.mockReturnValueOnce({ user: { user_id: "user-2", role: "case_manager" } })
        mockUseEffectivePermissions.mockReturnValueOnce({
            data: { permissions: ["view_donors", "edit_donors"] },
        })
        render(<DonorDetailPage />)
        expect(screen.getByPlaceholderText("Add a note...")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /Delete note from/ })).not.toBeInTheDocument()
    })

    it("renders and replaces the donor profile photo", async () => {
        mockUseDonor.mockReturnValue({
            ...mockUseDonor(),
            data: {
                ...mockUseDonor().data,
                profile_photo_attachment_id: "profile-1",
            },
        })
        mockUseAttachmentPreviewUrl.mockReturnValue({
            data: { download_url: "https://files.example/profile.jpg", filename: "profile.jpg" },
            isLoading: false,
        })
        render(<DonorDetailPage />)

        expect(screen.getByRole("img", { name: "Maya Thompson profile photo" })).toHaveAttribute(
            "data-src",
            "https://files.example/profile.jpg",
        )
        const image = new File(["image"], "replacement.jpg", { type: "image/jpeg" })
        const photoInput = screen.getByLabelText("Choose replacement donor profile photo")
        expect(photoInput).toHaveAttribute("accept", "image/jpeg,image/png")
        fireEvent.change(photoInput, {
            target: { files: [image] },
        })

        await vi.waitFor(() => expect(mockUploadDonorProfilePhoto).toHaveBeenCalledWith({
            donorId: "donor-1",
            file: image,
        }))
    })

    it("renders donor document loading, error/retry, and empty states", () => {
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
        vi.spyOn(window, "confirm").mockReturnValueOnce(true)
        render(<DonorDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Download screening.pdf" }))
        expect(mockDownloadAttachment).toHaveBeenCalledWith("attachment-1")
        fireEvent.click(screen.getByRole("button", { name: "Delete screening.pdf" }))

        await vi.waitFor(() => expect(mockDeleteDonorAttachment).toHaveBeenCalledWith({
            donorId: "donor-1",
            attachmentId: "attachment-1",
        }))
    })

    it("edits donor basic details without exposing donor type as mutable", async () => {
        render(<DonorDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Actions for Maya Thompson" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Edit" }))
        expect(screen.queryByLabelText("Donor type")).not.toBeInTheDocument()
        fireEvent.change(screen.getByLabelText("Education"), {
            target: { value: "M.S. Biology" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save Changes" }))

        await vi.waitFor(() => {
            expect(mockUpdateDonor).toHaveBeenCalledWith({
                id: "donor-1",
                data: expect.objectContaining({
                    full_name: "Maya Thompson",
                    email: "maya@example.com",
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

        await vi.waitFor(() => {
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

        await vi.waitFor(() => {
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

        await vi.waitFor(() => {
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

        expect(screen.getByRole("link", { name: "Back to donors" })).toHaveAttribute(
            "href",
            "/donors?type=sperm&stage=sperm-ready&q=maya&page=2",
        )
        expect(screen.getByRole("link", { name: "View full history →" })).toHaveAttribute(
            "href",
            "/donors/donor-1/history?return_to=%2Fdonors%3Ftype%3Dsperm%26stage%3Dsperm-ready%26q%3Dmaya%26page%3D2",
        )

        fireEvent.click(screen.getByRole("button", { name: "Actions for Maya Thompson" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Archive" }))

        await vi.waitFor(() => expect(mockArchiveDonor).toHaveBeenCalledWith("donor-1"))
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

        await vi.waitFor(() => expect(mockRestoreDonor).toHaveBeenCalledWith("donor-1"))
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
        expect(screen.getByRole("link", { name: "Back to donors" })).toHaveAttribute(
            "href",
            "/donors",
        )
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
        expect(screen.queryByRole("heading", { name: "Open Tasks" })).not.toBeInTheDocument()
    })

    it("keeps donor attachment mutations behind edit permission", () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_donors"] },
        })

        render(<DonorDetailPage />)
        expect(screen.queryByLabelText("Upload donor documents")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Delete screening.pdf" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Upload donor profile photo" })).not.toBeInTheDocument()
    })
})
