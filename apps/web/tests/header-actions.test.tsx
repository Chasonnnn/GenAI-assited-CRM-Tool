import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { HeaderActions } from "@/components/surrogates/detail/SurrogateDetailLayout/HeaderActions"

const mockUseAuth = vi.fn()
const mockUseSurrogateDetailLayout = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/components/surrogates/detail/SurrogateDetailLayout/context", () => ({
    useSurrogateDetailLayout: () => mockUseSurrogateDetailLayout(),
}))

describe("HeaderActions", () => {
    beforeEach(() => {
        mockUseAuth.mockReturnValue({
            user: { role: "admin", user_id: "user1" },
        })

        mockUseSurrogateDetailLayout.mockReturnValue({
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
            claimSurrogate: vi.fn(),
            assignSurrogate: vi.fn(),
            archiveSurrogate: vi.fn(),
            restoreSurrogate: vi.fn(),
            isClaimPending: false,
            isAssignPending: false,
            isReleasePending: false,
        })
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

        mockUseSurrogateDetailLayout.mockReturnValue({
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
            openDialog: vi.fn(),
            canManageQueue: false,
            canClaimSurrogate: false,
            canChangeStage: true,
            isInQueue: false,
            isOwnedByUser: true,
            zoomConnected: false,
            claimSurrogate: vi.fn(),
            assignSurrogate: vi.fn(),
            archiveSurrogate: vi.fn(),
            restoreSurrogate: vi.fn(),
            isClaimPending: false,
            isAssignPending: false,
            isReleasePending: false,
        })

        render(<HeaderActions />)
        expect(screen.getByRole("button", { name: /log contact/i })).toBeInTheDocument()
    })
})
