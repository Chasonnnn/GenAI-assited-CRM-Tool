import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import SurrogateProfilePage from "@/app/(app)/surrogates/[id]/profile/page"
import SurrogateJourneyPage from "@/app/(app)/surrogates/[id]/journey/page"

const state = vi.hoisted(() => ({
    role: "operations",
    policyVersion: 2,
    permissions: ["view_surrogates"] as string[],
    sync: vi.fn(),
    save: vi.fn(),
    hide: vi.fn(),
}))
const detail = () => ({
    surrogateId: "surrogate-1",
    canViewProfile: true,
    canViewJourney: true,
    effectivePermissions: { policy_version: state.policyVersion, permissions: state.permissions },
    canEditSurrogate: state.policyVersion !== 2 || state.permissions.includes("edit_surrogates"),
})
vi.mock("@/components/surrogates/detail/SurrogateDetailLayout/context", () => ({ useSurrogateDetailData: () => detail() }))
vi.mock("@/components/surrogates/detail/SurrogateDetailLayout", () => ({ useSurrogateDetailData: () => detail() }))
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "surrogate-1" }) }))
vi.mock("@/components/ui/tabs", () => ({ TabsContent: ({ children }: { children: ReactNode }) => <div>{children}</div> }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { role: state.role, user_id: "user-1" } }) }))
vi.mock("@/lib/hooks/use-profile", () => ({
    useProfile: () => ({ data: {
        base_submission_id: "submission-1",
        overrides: {}, hidden_fields: [], merged_view: { full_name: "Synthetic Applicant" }, base_answers: { full_name: "Synthetic Applicant" },
        schema_snapshot: { pages: [{ title: "Applicant", fields: [{ key: "full_name", type: "text", label: "Full name" }] }] },
        custom_qas: [],
    }, isLoading: false, error: null }),
    useSyncProfile: () => ({ mutateAsync: state.sync, isPending: false }),
    useSaveProfileOverrides: () => ({ mutateAsync: state.save, isPending: false }),
    useToggleProfileHidden: () => ({ mutateAsync: state.hide, isPending: false }),
}))
vi.mock("@/lib/hooks/use-journey", () => ({
    useSurrogateJourney: () => ({ data: {
        surrogate_id: "surrogate-1", surrogate_name: "Synthetic Applicant", organization_name: "Synthetic Org", phases: [{
            slug: "matching", label: "Matching", milestones: [{ slug: "match_confirmed", label: "Match Confirmed", status: "completed", completed_at: "2026-09-01T12:00:00Z", featured_image_id: null }],
        }],
    }, isLoading: false, error: null }),
}))
vi.mock("@/components/surrogates/journey/MilestoneImageSelector", () => ({
    MilestoneImageSelector: ({ open }: { open: boolean }) => open ? <div role="dialog" aria-label="Choose milestone image" /> : null,
}))

beforeEach(() => {
    state.role = "operations"
    state.policyVersion = 2
    state.permissions = ["view_surrogates"]
    vi.clearAllMocks()
})

describe("Surrogate Profile permission controls", () => {
    it("keeps Operations profile readable and disables edit and sync", () => {
        render(<SurrogateProfilePage />)
        expect(screen.getAllByText("Synthetic Applicant").length).toBeGreaterThan(0)
        expect(screen.getByRole("button", { name: /^Edit$/ })).toBeDisabled()
        fireEvent.click(screen.getByRole("button", { name: "Sync" }))
        expect(screen.getByRole("button", { name: "Sync" })).toBeDisabled()
        expect(state.sync).not.toHaveBeenCalled()
        expect(screen.getByRole("button", { name: "Export" })).toBeEnabled()
    })

    it("allows delegated edits and closes field editors when the grant is revoked", () => {
        state.permissions.push("edit_surrogates")
        const view = render(<SurrogateProfilePage />)
        fireEvent.click(screen.getByRole("button", { name: /^Edit$/ }))
        expect(screen.getByPlaceholderText("Profile header name")).toBeInTheDocument()
        fireEvent.change(screen.getByPlaceholderText("Profile header name"), { target: { value: "Edited Applicant" } })
        expect(screen.getByRole("button", { name: "Save Changes" })).toBeEnabled()
        state.permissions = ["view_surrogates"]
        view.rerender(<SurrogateProfilePage />)
        expect(screen.queryByPlaceholderText("Profile header name")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Save Changes" })).not.toBeInTheDocument()
        expect(state.save).not.toHaveBeenCalled()
    })
})

describe("Surrogate Journey permission controls", () => {
    it("shows Operations the journey without photo editing", () => {
        render(<SurrogateJourneyPage />)
        expect(screen.getAllByText("Match Confirmed").length).toBeGreaterThan(0)
        expect(screen.queryByRole("button", { name: "Set Image" })).not.toBeInTheDocument()
    })

    it("uses delegated edit permission and closes the selector after revocation", () => {
        state.permissions.push("edit_surrogates")
        const view = render(<SurrogateJourneyPage />)
        fireEvent.click(screen.getAllByRole("button", { name: "Set Image" })[0])
        expect(screen.getByRole("dialog", { name: "Choose milestone image" })).toBeInTheDocument()
        state.permissions = ["view_surrogates"]
        view.rerender(<SurrogateJourneyPage />)
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Set Image" })).not.toBeInTheDocument()
    })

    it("preserves legacy Case Manager editing", () => {
        state.policyVersion = 1
        state.role = "case_manager"
        render(<SurrogateJourneyPage />)
        expect(screen.getAllByRole("button", { name: "Set Image" }).length).toBeGreaterThan(0)
    })
})
