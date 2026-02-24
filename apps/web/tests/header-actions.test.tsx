import { describe, expect, it, vi, beforeEach } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { HeaderActions } from "@/components/surrogates/detail/SurrogateDetailLayout/HeaderActions"

const mockUseAuth = vi.fn()
const mockUseSurrogateDetailData = vi.fn()
const mockUseSurrogateDetailDialogs = vi.fn()
const mockUseSurrogateDetailActions = vi.fn()
const mockExportSurrogatePacketPdf = vi.fn()
const mockToastSuccess = vi.fn()
const mockToastError = vi.fn()

vi.mock("@/components/ui/dropdown-menu", () => ({
    DropdownMenu: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuTrigger: ({
        children,
        ...props
    }: {
        children: ReactNode
        [key: string]: unknown
    }) => <button {...props}>{children}</button>,
    DropdownMenuContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuItem: ({
        children,
        onClick,
        disabled,
        className,
    }: {
        children: ReactNode
        onClick?: () => void
        disabled?: boolean
        className?: string
    }) => (
        <button onClick={onClick} disabled={disabled} className={className}>
            {children}
        </button>
    ),
    DropdownMenuSeparator: () => <hr />,
    DropdownMenuSub: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DropdownMenuSubTrigger: ({
        children,
        disabled,
    }: {
        children: ReactNode
        disabled?: boolean
    }) => <button disabled={disabled}>{children}</button>,
    DropdownMenuSubContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/api/surrogates", () => ({
    exportSurrogatePacketPdf: (...args: unknown[]) => mockExportSurrogatePacketPdf(...args),
}))

vi.mock("sonner", () => ({
    toast: {
        success: (...args: unknown[]) => mockToastSuccess(...args),
        error: (...args: unknown[]) => mockToastError(...args),
    },
}))

vi.mock("@/components/surrogates/detail/SurrogateDetailLayout/context", () => ({
    useSurrogateDetailData: () => mockUseSurrogateDetailData(),
    useSurrogateDetailDialogs: () => mockUseSurrogateDetailDialogs(),
    useSurrogateDetailActions: () => mockUseSurrogateDetailActions(),
}))

describe("HeaderActions", () => {
    beforeEach(() => {
        mockUseAuth.mockReturnValue({
            user: { role: "admin", user_id: "user1" },
        })

        mockUseSurrogateDetailData.mockReturnValue({
            surrogate: {
                id: "s1",
                stage_id: "stage_new_unread",
                owner_type: "user",
                owner_id: "user1",
                is_archived: false,
                surrogate_number: "S123",
                full_name: "Jane Doe",
            },
            stageById: new Map([
                [
                    "stage_new_unread",
                    { slug: "new_unread", stage_type: "intake", order: 1 },
                ],
            ]),
            stageOptions: [{ slug: "contacted", stage_type: "intake", order: 2 }],
            queues: [],
            assignees: [],
            openDialog: vi.fn(),
            canManageQueue: true,
            canClaimSurrogate: false,
            canChangeStage: true,
            isInQueue: false,
            isOwnedByUser: true,
            zoomConnected: false,
        })
        mockUseSurrogateDetailDialogs.mockReturnValue({
            openDialog: vi.fn(),
        })
        mockUseSurrogateDetailActions.mockReturnValue({
            claimSurrogate: vi.fn(),
            assignSurrogate: vi.fn(),
            archiveSurrogate: vi.fn(),
            restoreSurrogate: vi.fn(),
            isClaimPending: false,
            isAssignPending: false,
            isReleasePending: false,
        })
        mockExportSurrogatePacketPdf.mockReset()
        mockToastSuccess.mockReset()
        mockToastError.mockReset()
    })

    it("renders 'More actions' button with accessible label", () => {
        render(<HeaderActions />)
        const button = screen.getByRole("button", { name: /more actions/i })
        expect(button).toBeInTheDocument()
    })

    it("shows Log Contact for intake assignee in new unread even when stage order is custom", () => {
        mockUseAuth.mockReturnValue({
            user: { role: "intake_specialist", user_id: "intake-user-1" },
        })

        mockUseSurrogateDetailData.mockReturnValue({
            surrogate: {
                id: "s1",
                stage_id: "stage_new_unread",
                owner_type: "user",
                owner_id: "intake-user-1",
                is_archived: false,
                surrogate_number: "S123",
                full_name: "Jane Doe",
            },
            stageById: new Map([
                [
                    "stage_new_unread",
                    { slug: "new_unread", stage_type: "intake", order: 10 },
                ],
            ]),
            stageOptions: [{ slug: "contacted", stage_type: "intake", order: 2 }],
            queues: [],
            assignees: [],
            canManageQueue: false,
            canClaimSurrogate: false,
            canChangeStage: true,
            isInQueue: false,
            isOwnedByUser: true,
            zoomConnected: false,
        })

        render(<HeaderActions />)
        expect(screen.getByRole("button", { name: /log contact/i })).toBeInTheDocument()
    })

    it("hides Log Contact once surrogate is past contacted", () => {
        mockUseAuth.mockReturnValue({
            user: { role: "intake_specialist", user_id: "intake-user-1" },
        })

        mockUseSurrogateDetailData.mockReturnValue({
            surrogate: {
                id: "s1",
                stage_id: "stage_qualified",
                owner_type: "user",
                owner_id: "intake-user-1",
                is_archived: false,
                surrogate_number: "S123",
                full_name: "Jane Doe",
                stage_slug: "qualified",
            },
            stageById: new Map([
                [
                    "stage_qualified",
                    { slug: "qualified", stage_type: "intake", order: 3 },
                ],
            ]),
            stageOptions: [],
            queues: [],
            assignees: [],
            canManageQueue: false,
            canClaimSurrogate: false,
            canChangeStage: true,
            isInQueue: false,
            isOwnedByUser: true,
            zoomConnected: false,
        })

        render(<HeaderActions />)
        expect(screen.queryByRole("button", { name: /log contact/i })).not.toBeInTheDocument()
    })

    it("hides Log Interview Outcome before interview scheduled", () => {
        mockUseAuth.mockReturnValue({
            user: { role: "intake_specialist", user_id: "intake-user-1" },
        })

        mockUseSurrogateDetailData.mockReturnValue({
            surrogate: {
                id: "s1",
                stage_id: "stage_contacted",
                owner_type: "user",
                owner_id: "intake-user-1",
                is_archived: false,
                surrogate_number: "S123",
                full_name: "Jane Doe",
                stage_slug: "contacted",
            },
            stageById: new Map([
                [
                    "stage_contacted",
                    { slug: "contacted", stage_type: "intake", order: 2 },
                ],
            ]),
            stageOptions: [],
            queues: [],
            assignees: [],
            canManageQueue: false,
            canClaimSurrogate: false,
            canChangeStage: true,
            isInQueue: false,
            isOwnedByUser: true,
            zoomConnected: false,
        })

        render(<HeaderActions />)
        expect(screen.queryByRole("button", { name: /log interview outcome/i })).not.toBeInTheDocument()
    })

    it("shows Log Interview Outcome at interview scheduled", () => {
        mockUseAuth.mockReturnValue({
            user: { role: "intake_specialist", user_id: "intake-user-1" },
        })

        mockUseSurrogateDetailData.mockReturnValue({
            surrogate: {
                id: "s1",
                stage_id: "stage_interview_scheduled",
                owner_type: "user",
                owner_id: "intake-user-1",
                is_archived: false,
                surrogate_number: "S123",
                full_name: "Jane Doe",
                stage_slug: "interview_scheduled",
            },
            stageById: new Map([
                [
                    "stage_interview_scheduled",
                    { slug: "interview_scheduled", stage_type: "intake", order: 5 },
                ],
            ]),
            stageOptions: [],
            queues: [],
            assignees: [],
            canManageQueue: false,
            canClaimSurrogate: false,
            canChangeStage: true,
            isInQueue: false,
            isOwnedByUser: true,
            zoomConnected: false,
        })

        render(<HeaderActions />)
        expect(screen.getByRole("button", { name: /log interview outcome/i })).toBeInTheDocument()
    })

    it("disables export action while request is in progress", async () => {
        let resolveExport: ((value: { includesApplication: boolean }) => void) | null = null
        mockExportSurrogatePacketPdf.mockReturnValue(
            new Promise((resolve) => {
                resolveExport = resolve
            })
        )

        render(<HeaderActions />)
        const exportButton = screen.getByRole("button", { name: /^export$/i })
        fireEvent.click(exportButton)

        await waitFor(() => {
            expect(mockExportSurrogatePacketPdf).toHaveBeenCalledWith("s1")
        })
        expect(exportButton).toBeDisabled()

        resolveExport?.({ includesApplication: false })
        await waitFor(() => {
            expect(exportButton).not.toBeDisabled()
        })
    })

    it("exports combined packet and shows combined success toast", async () => {
        mockExportSurrogatePacketPdf.mockResolvedValue({ includesApplication: true })

        render(<HeaderActions />)
        fireEvent.click(screen.getByRole("button", { name: /^export$/i }))

        await waitFor(() => {
            expect(mockExportSurrogatePacketPdf).toHaveBeenCalledWith("s1")
        })
        expect(mockToastSuccess).toHaveBeenCalledWith("Exported case details + application")
        expect(mockToastError).not.toHaveBeenCalled()
    })

    it("exports case details only and shows no-application success toast", async () => {
        mockExportSurrogatePacketPdf.mockResolvedValue({ includesApplication: false })

        render(<HeaderActions />)
        fireEvent.click(screen.getByRole("button", { name: /^export$/i }))

        await waitFor(() => {
            expect(mockExportSurrogatePacketPdf).toHaveBeenCalledWith("s1")
        })
        expect(mockToastSuccess).toHaveBeenCalledWith(
            "Exported case details (no submitted application yet)"
        )
    })

    it("shows failure toast when export fails", async () => {
        mockExportSurrogatePacketPdf.mockRejectedValue(new Error("boom"))

        render(<HeaderActions />)
        fireEvent.click(screen.getByRole("button", { name: /^export$/i }))

        await waitFor(() => {
            expect(mockToastError).toHaveBeenCalledWith("Failed to export")
        })
    })
})
