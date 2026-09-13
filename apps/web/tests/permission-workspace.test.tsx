import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within, waitFor } from "@testing-library/react"
import { PermissionWorkspace } from "@/components/permissions/permission-workspace"

const state = vi.hoisted(() => ({ enriched: false, version: 2, aiEnabled: true, authorized: true, loading: false, error: null as Error | null, empty: false, saveError: null as Error | null, save: vi.fn(), retry: vi.fn() }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { user_id: "admin-user" } }) }))
vi.mock("@/components/app-link", () => ({ default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={href} {...props}>{children}</a> }))
vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({ data: { permissions: [], capabilities: { can_manage_roles: state.authorized } } }),
    useRoles: () => ({ data: state.empty ? [] : [{ role: "case_manager", label: "Case Manager" }, { role: "admin", label: "Admin", protected: true }], isLoading: state.loading, error: state.error, refetch: state.retry }),
    useRoleDetail: (role: string) => ({ data: state.empty ? undefined : { role, label: role === "admin" ? "Admin" : "Case Manager", protected: role === "admin", can_edit: role !== "admin", policy_version: state.version, included_features: { personal_workspace: true, ai_assistant: state.aiEnabled }, permissions_by_category: { ...(state.enriched ? { Donors: [{ key: "archive_donors", label: "Archive Donors", short_label: "Archive", topic: "Donors", section: "Records", is_granted: false }, { key: "view_donors", label: "View Donors", short_label: "View", topic: "Donors", section: "Records", is_granted: true }, { key: "create_donors", label: "Create Donors", short_label: "Create", topic: "Donors", section: "Records", is_granted: false }, { key: "assign_donors", label: "Assign Donors", short_label: "Assign", topic: "Donors", section: "Progress & ownership", is_granted: false }, { key: "approve_donors", label: "Approve Donors", short_label: "Approve", topic: "Donors", section: "Progress & ownership", is_granted: false }, { key: "change_donor_status", label: "Change Donor Status", short_label: "Change status", topic: "Donors", section: "Progress & ownership", is_granted: false }], Other: [{ key: "view_notes", label: "View Notes", short_label: "View", topic: "Surrogates", section: "Notes", is_granted: true }, { key: "edit_notes", label: "Edit Notes", short_label: "Edit", topic: "Surrogates", section: "Notes", is_granted: true }, { key: "manage_automation", label: "Manage Personal Workflows", short_label: "Personal workflows", topic: "Operations", section: "Workflows", is_granted: true, is_default: true }, { key: "manage_org_workflows", label: "Manage Organization Workflows", short_label: "Manage", topic: "Operations", section: "Workflows", is_granted: false }, { key: "manage_org_templates", label: "Manage Organization Templates", short_label: "Manage", topic: "Operations", section: "Templates", is_granted: false }, { key: "send_campaigns", label: "Send Campaigns", short_label: "Send", topic: "Operations", section: "Campaigns", is_granted: false }, { key: "view_reports", label: "View Reports", short_label: "View", topic: "Operations", section: "Reports", is_granted: false }, { key: "use_ai_assistant", label: "Use AI Assistant", short_label: "Use AI", topic: "Administration", section: "AI", is_granted: true, is_default: true }, { key: "manage_ai_settings", label: "Manage AI Settings", short_label: "Manage settings", topic: "Administration", section: "AI", is_granted: false, configurable: false }] } : {}), Surrogates: [{ key: "view_surrogates", label: "View Surrogates", short_label: state.enriched ? "View" : undefined, topic: "Surrogates", section: "Records", is_granted: true, configurable: true }, { key: "edit_surrogates", label: "Edit Surrogates", short_label: state.enriched ? "Edit" : undefined, topic: "Surrogates", section: "Records", is_granted: false, configurable: true }] } }, isLoading: state.loading, error: state.error, refetch: state.retry }),
    useUpdateRolePermissions: () => ({ mutateAsync: state.save, isPending: false, error: state.saveError, reset: vi.fn() }),
}))
vi.mock("@/lib/hooks/use-record-scopes", () => ({ useRoleScopes: () => ({ data: { surrogates: { assignment: "assigned", phase: "post_approval", stage_ids: [] } }, isLoading: false }) }))
vi.mock("@/lib/hooks/use-pipelines", () => ({ usePipelines: () => ({ data: [{ id: "pipeline", name: "Surrogate pipeline", stages: [{ id: "approved-stage", label: "Approved" }] }], isLoading: false }) }))
vi.mock("@/components/permissions/permission-policy-review", () => ({ PermissionPolicyReview: () => <div>Policy review</div> }))
vi.mock("@/components/permissions/permission-access-checker", () => ({ PermissionAccessChecker: () => <div>Access checker</div> }))

describe("permission role workspace", () => {
    beforeEach(() => { state.enriched = false; state.version = 2; state.aiEnabled = true; state.authorized = true; state.loading = false; state.error = null; state.empty = false; state.saveError = null; state.save.mockReset().mockResolvedValue({}); state.retry.mockReset() })

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
        fireEvent.click(screen.getByRole("button", { name: "Admin", exact: true }))
        fireEvent.click(screen.getByRole("button", { name: "Keep editing" }))
        expect(screen.getByRole("switch", { name: "Edit Surrogates" })).toBeChecked()
        fireEvent.click(screen.getByRole("button", { name: "Admin", exact: true }))
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
    it("groups records into five topics with short actions and operation subtopics", () => {
        state.enriched = true
        render(<PermissionWorkspace />)
        const navigation = screen.getByRole("navigation", { name: "Permission modules" })
        for (const topic of ["Surrogates", "Donors", "Intended Parents", "Operations", "Administration"]) {
            expect(within(navigation).getByRole("button", { name: topic, exact: true })).toBeVisible()
        }
        fireEvent.click(within(navigation).getByRole("button", { name: "Donors", exact: true }))
        expect(screen.getByRole("heading", { name: "Records", exact: true })).toBeVisible()
        expect(screen.getByRole("heading", { name: "Progress & ownership" })).toBeVisible()
        expect(screen.getByRole("switch", { name: "Create", exact: true })).not.toBeChecked()
        fireEvent.click(screen.getByRole("switch", { name: "Create", exact: true }))
        fireEvent.click(within(navigation).getByRole("button", { name: "Operations", exact: true }))
        fireEvent.click(within(navigation).getByRole("button", { name: "Reports", exact: true }))
        fireEvent.click(screen.getByRole("switch", { name: "View", exact: true }))
        fireEvent.click(screen.getByRole("button", { name: "Review changes" }))
        expect(screen.getByRole("dialog")).toHaveTextContent("Create Donors")
        expect(screen.getByRole("dialog")).toHaveTextContent("View Reports")
    })

    it("keeps universal defaults in the preview and reports the actual organization AI setting", () => {
        state.enriched = true
        state.aiEnabled = false
        render(<PermissionWorkspace />)
        fireEvent.click(screen.getByRole("button", { name: "Operations", exact: true }))
        fireEvent.click(screen.getByRole("button", { name: "Workflows", exact: true }))
        expect(screen.queryByRole("switch", { name: "Personal workflows" })).not.toBeInTheDocument()
        expect(screen.getByRole("switch", { name: "Manage", exact: true })).toBeVisible()
        fireEvent.click(screen.getByRole("button", { name: "Administration", exact: true }))
        expect(screen.queryByRole("switch", { name: "Use AI" })).not.toBeInTheDocument()
        expect(screen.getByRole("switch", { name: "Manage settings" })).toHaveAttribute("aria-disabled", "true")
        const preview = screen.getByRole("complementary", { name: "Access preview" })
        expect(within(preview).getByText("Personal workspace")).toBeVisible()
        expect(within(preview).getByText("AI Assistant")).toBeVisible()
        expect(within(preview).getByText("Disabled")).toBeVisible()
        expect(screen.queryByText("Use AI Assistant")).not.toBeInTheDocument()
    })

    it("retains legacy default controls until the policy is activated", () => {
        state.enriched = true
        state.version = 1
        render(<PermissionWorkspace />)
        fireEvent.click(screen.getByRole("button", { name: "Operations", exact: true }))
        fireEvent.click(screen.getByRole("button", { name: "Workflows", exact: true }))
        expect(screen.getByRole("switch", { name: "Personal workflows" })).toBeVisible()
        expect(screen.queryByText("Included for everyone")).not.toBeInTheDocument()
    })

    it("keeps Operations topics collapsed until Operations is selected", () => {
        state.enriched = true
        render(<PermissionWorkspace />)
        expect(screen.queryByRole("button", { name: "Workflows", exact: true })).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Operations", exact: true })).toHaveAttribute("aria-expanded", "false")
        fireEvent.click(screen.getByRole("button", { name: "Operations", exact: true }))
        expect(screen.getByRole("button", { name: "Workflows", exact: true })).toBeVisible()
        fireEvent.click(screen.getByRole("button", { name: "Donors", exact: true }))
        expect(screen.queryByRole("button", { name: "Workflows", exact: true })).not.toBeInTheDocument()
    })

    it("orders record sections before notes and qualifies only ambiguous preview actions", () => {
        state.enriched = true
        render(<PermissionWorkspace />)
        const editor = screen.getByRole("region", { name: "Surrogates permissions" })
        expect(within(editor).getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent)).toEqual(["Record scope", "Records", "Notes"])
        expect(within(editor).getAllByRole("switch", { name: "View", exact: true })).toHaveLength(2)
        const preview = screen.getByRole("complementary", { name: "Access preview" })
        expect(within(preview).getByText("View", { exact: true })).toBeVisible()
        expect(within(preview).getByText("View notes", { exact: true })).toBeVisible()
        expect(within(preview).getByText("Edit notes", { exact: true })).toBeVisible()
        fireEvent.click(screen.getByRole("button", { name: "Donors", exact: true }))
        expect(within(screen.getByRole("region", { name: "Donors permissions" })).getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent)).toEqual(["Record scope", "Records", "Progress & ownership"])
    })

    it("orders record and progress actions by their task sequence", () => {
        state.enriched = true
        render(<PermissionWorkspace />)
        fireEvent.click(screen.getByRole("button", { name: "Donors", exact: true }))
        const editor = screen.getByRole("region", { name: "Donors permissions" })
        expect(within(editor).getAllByRole("switch").map((control) => control.closest("label")?.textContent)).toEqual(["View", "Create", "Archive", "Change status", "Approve", "Assign"])
    })

})
