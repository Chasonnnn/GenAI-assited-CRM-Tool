import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { HeaderActions } from "@/components/surrogates/detail/SurrogateDetailLayout/HeaderActions"

// Mock the hooks
vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({
        user: { role: "admin", user_id: "user1" }
    })
}))

vi.mock("@/components/surrogates/detail/SurrogateDetailLayout/context", () => ({
    useSurrogateDetailLayout: () => ({
        surrogate: {
            id: "s1",
            stage_id: "stage1",
            owner_type: "user",
            owner_id: "user1",
            is_archived: false,
            surrogate_number: "S123",
            full_name: "Jane Doe"
        },
        stageById: new Map([["stage1", { slug: "intake", stage_type: "intake", order: 1 }]]),
        stageOptions: [{ slug: "contacted", order: 2 }],
        queues: [],
        assignees: [],
        openDialog: vi.fn(),
        canManageQueue: true,
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
}))

describe("HeaderActions", () => {
    it("renders 'More actions' button with accessible label", () => {
        render(<HeaderActions />)
        // This is expected to fail before the fix
        const button = screen.getByRole("button", { name: /more actions/i })
        expect(button).toBeInTheDocument()
    })
})
