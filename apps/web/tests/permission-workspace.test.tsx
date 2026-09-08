import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within, waitFor } from "@testing-library/react"
import { PermissionWorkspace } from "@/components/permissions/permission-workspace"

const state = vi.hoisted(() => ({ authorized: true, loading: false, error: null as Error | null, empty: false, saveError: null as Error | null, save: vi.fn(), retry: vi.fn() }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { user_id: "admin-user" } }) }))
vi.mock("@/components/app-link", () => ({ default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={href} {...props}>{children}</a> }))
vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({ data: { permissions: [], capabilities: { can_manage_roles: state.authorized } } }),
    useRoles: () => ({ data: state.empty ? [] : [{ role: "case_manager", label: "Case Manager" }, { role: "admin", label: "Admin", protected: true }], isLoading: state.loading, error: state.error, refetch: state.retry }),
    useRoleDetail: (role: string) => ({ data: state.empty ? undefined : { role, label: role === "admin" ? "Admin" : "Case Manager", protected: role === "admin", can_edit: role !== "admin", policy_version: 2, permissions_by_category: { Surrogates: [{ key: "view_surrogates", label: "View Surrogates", is_granted: true, configurable: true }, { key: "edit_surrogates", label: "Edit Surrogates", is_granted: false, configurable: true }] } }, isLoading: state.loading, error: state.error, refetch: state.retry }),
    useUpdateRolePermissions: () => ({ mutateAsync: state.save, isPending: false, error: state.saveError, reset: vi.fn() }),
}))
vi.mock("@/lib/hooks/use-record-scopes", () => ({ useRoleScopes: () => ({ data: { surrogates: { assignment: "assigned", phase: "post_approval", stage_ids: [] } }, isLoading: false }) }))
vi.mock("@/lib/hooks/use-pipelines", () => ({ usePipelines: () => ({ data: [{ id: "pipeline", name: "Surrogate pipeline", stages: [{ id: "approved-stage", label: "Approved" }] }], isLoading: false }) }))
vi.mock("@/components/permissions/permission-policy-review", () => ({ PermissionPolicyReview: () => <div>Policy review</div> }))
vi.mock("@/components/permissions/permission-access-checker", () => ({ PermissionAccessChecker: () => <div>Access checker</div> }))

describe("permission role workspace", () => {
    beforeEach(() => { state.authorized = true; state.loading = false; state.error = null; state.empty = false; state.saveError = null; state.save.mockReset().mockResolvedValue({}); state.retry.mockReset() })

    it("renders one denied state without management navigation", () => {
        state.authorized = false
        render(<PermissionWorkspace />)
        expect(screen.getByRole("heading", { name: "Permissions unavailable" })).toBeVisible()
        expect(screen.queryByRole("navigation")).not.toBeInTheDocument()
        expect(screen.queryByRole("link", { name: "People" })).not.toBeInTheDocument()
    })

    it("renders loading, empty, and retryable error states", async () => {
        state.loading = true
        const view = render(<PermissionWorkspace />)
        expect(screen.getAllByRole("status")[0]).toHaveTextContent("Loading permissions")
        state.loading = false
        state.empty = true
        view.rerender(<PermissionWorkspace />)
        expect(screen.getByText("No roles available.")).toBeVisible()
        state.empty = false
        state.error = new Error("Permissions unavailable")
        view.rerender(<PermissionWorkspace />)
        expect(screen.getAllByRole("alert")[0]).toHaveTextContent("Permissions unavailable")
        fireEvent.click(screen.getAllByRole("button", { name: "Try again" })[0]!)
        expect(state.retry).toHaveBeenCalledOnce()
    })

    it("displays labels and reviews an atomic action and record scope save", async () => {
        render(<PermissionWorkspace />)
        expect(screen.getByRole("combobox", { name: "Assignment" })).toHaveTextContent("Assigned records")
        expect(screen.getByRole("combobox", { name: "Phase" })).toHaveTextContent("After approval")
        fireEvent.click(screen.getByRole("switch", { name: "Edit Surrogates" }))
        fireEvent.click(screen.getByRole("combobox", { name: "Assignment" }))
        fireEvent.mouseMove(screen.getByRole("option", { name: "All records" }))
        fireEvent.click(screen.getByRole("option", { name: "All records" }))
        expect(state.save).not.toHaveBeenCalled()
        fireEvent.click(screen.getByRole("button", { name: "Review changes" }))
        const dialog = screen.getByRole("dialog")
        expect(dialog).toHaveTextContent("Edit Surrogates")
        expect(dialog).toHaveTextContent("All records · After approval")
        fireEvent.click(within(dialog).getByRole("button", { name: "Apply changes" }))
        await waitFor(() => expect(state.save).toHaveBeenCalledWith({ role: "case_manager", permissions: { edit_surrogates: true }, scopeRules: { surrogates: { assignment: "all", phase: "post_approval", stage_ids: [] } } }))
        await waitFor(() => expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument())
    })

    it("protects Admin switches and record scope controls", () => {
        render(<PermissionWorkspace initialRole="admin" />)
        expect(screen.getByText("This role’s baseline cannot be changed.")).toBeVisible()
        screen.getAllByRole("switch").forEach((control) => expect(control).toHaveAttribute("aria-disabled", "true"))
        expect(screen.getByRole("combobox", { name: "Assignment" })).toBeDisabled()
        expect(screen.queryByRole("button", { name: "Review changes" })).not.toBeInTheDocument()
    })

    it("keeps edits when role navigation is cancelled and discards only after confirmation", async () => {
        render(<PermissionWorkspace />)
        fireEvent.click(screen.getByRole("switch", { name: "Edit Surrogates" }))
        fireEvent.click(screen.getByRole("button", { name: /Admin/ }))
        fireEvent.click(screen.getByRole("button", { name: "Keep editing" }))
        expect(screen.getByRole("switch", { name: "Edit Surrogates" })).toBeChecked()
        fireEvent.click(screen.getByRole("button", { name: /Admin/ }))
        fireEvent.click(screen.getByRole("button", { name: "Discard changes" }))
        expect(screen.getByText("This role’s baseline cannot be changed.")).toBeVisible()
        expect(state.save).not.toHaveBeenCalled()
    })

    it("keeps the review open when the server rejects a save", async () => {
        state.save.mockRejectedValue(new Error("Access changed; retry"))
        render(<PermissionWorkspace />)
        fireEvent.click(screen.getByRole("switch", { name: "Edit Surrogates" }))
        fireEvent.click(screen.getByRole("button", { name: "Review changes" }))
        fireEvent.click(screen.getByRole("button", { name: "Apply changes" }))
        await waitFor(() => expect(state.save).toHaveBeenCalledOnce())
        expect(screen.getByRole("dialog")).toBeVisible()
        expect(screen.getByText("Unsaved changes")).toBeVisible()
    })
})
