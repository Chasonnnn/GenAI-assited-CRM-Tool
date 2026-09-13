import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { PermissionMemberDetail } from "@/components/permissions/permission-member-detail"
import * as api from "@/lib/api/permissions"
import * as scopes from "@/lib/api/record-scopes"

vi.mock("@/lib/api/permissions", async (original) => ({ ...await original<typeof api>(), getMember: vi.fn(), getMyEffectivePermissions: vi.fn(), getRoles: vi.fn(), getRoleDetail: vi.fn(), getAvailablePermissions: vi.fn(), updateMember: vi.fn(), removeMember: vi.fn() }))
vi.mock("@/lib/api/record-scopes", async (original) => ({ ...await original<typeof scopes>(), getRoleScopes: vi.fn(), getScopeAdditions: vi.fn(), getScopeMigrationReview: vi.fn(), addScopeAddition: vi.fn(), removeScopeAddition: vi.fn(), addCollaborator: vi.fn(), removeCollaborator: vi.fn() }))
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { user_id: "admin-user" } }) }))
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock("@/components/app-link", () => ({ default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={href} {...props}>{children}</a> }))
vi.mock("@/lib/hooks/use-pipelines", () => ({ usePipelines: () => ({ data: [], isLoading: false }) }))

const member: api.MemberDetail = { id: "member-1", user_id: "user-1", display_name: "Taylor Morgan", email: "taylor@example.test", role: "case_manager", is_active: true, created_at: "2026-09-07", last_login_at: null, policy_version: 2, capabilities: { can_manage_members: true, can_add_permissions: true }, effective_permissions: ["view_surrogates", "send_email"], overrides: [{ permission: "send_email", label: "Send Email", category: "Communications", override_type: "grant" }], access_sources: { view_surrogates: ["role_baseline"], send_email: ["individual_addition"] } }
function choose(label: string | RegExp, option: string) { fireEvent.click(screen.getByRole("combobox", { name: label })); const item = screen.getByRole("option", { name: option }); fireEvent.mouseMove(item); fireEvent.click(item) }

describe("member permission administration", () => {
    beforeEach(() => {
        vi.mocked(api.getMember).mockReset().mockResolvedValue(member)
        vi.mocked(api.getMyEffectivePermissions).mockReset().mockResolvedValue({ user_id: "admin-user", role: "admin", permissions: [], overrides: [], policy_version: 2, capabilities: { can_manage_roles: true, can_assign_developer: false } })
        vi.mocked(api.getRoles).mockReset().mockResolvedValue([{ role: "case_manager", label: "Case Manager", permission_count: 1, is_developer: false }, { role: "operations", label: "Operations", permission_count: 1, is_developer: false }])
        vi.mocked(api.getRoleDetail).mockReset().mockImplementation(async (role) => ({ role, label: role, protected: false, permissions_by_category: { Surrogates: [{ key: "view_surrogates", label: "View Surrogates", description: "", is_granted: true, developer_only: false }, { key: "send_email", label: "Send Email", description: "", is_granted: false, developer_only: false }] } }))
        vi.mocked(api.getAvailablePermissions).mockReset().mockResolvedValue([...["view_surrogates", "send_email", "view_reports"].map((key) => ({ key, label: { view_surrogates: "View Surrogates", send_email: "Send Email", view_reports: "View Reports" }[key]!, category: "Actions", description: "", developer_only: false, assignable: true })), { key: "manage_roles", label: "Manage Roles", category: "Administration", description: "", developer_only: false, assignable: false }])
        vi.mocked(scopes.getRoleScopes).mockReset().mockImplementation(async (role) => ({ surrogates: { assignment: role === "operations" ? "all" : "assigned", phase: role === "operations" ? "all" : "post_approval", stage_ids: [] }, donors: { assignment: "all", phase: "post_approval", stage_ids: [] }, intended_parents: { assignment: "all", phase: "all", stage_ids: [] } }))
        vi.mocked(scopes.getScopeAdditions).mockReset().mockResolvedValue([{ id: "scope-1", user_id: member.user_id, module: "surrogates", assignment: "all", phase: "pre_approval", stage_ids: [], created_at: "2026-09-07" }])
        vi.mocked(scopes.getScopeMigrationReview).mockReset().mockResolvedValue({ ready: true, collaborators: [{ id: "collab-1", user_id: member.user_id, surrogate_id: "surrogate-1", donor_id: null }], handoff_candidates: [], unresolved_handoffs: [], missing_approval_gate_pipeline_ids: [], legacy_pool_grants: [] })
        vi.mocked(api.updateMember).mockReset().mockResolvedValue(member)
    })

    it("shows inherited permissions separately and only offers additive grants", async () => {
        render(<PermissionMemberDetail memberId="member-1" />)
        await screen.findByText("Individual additions")
        const roleSection = screen.getByText("Role permissions").closest("section")!
        expect(await within(roleSection).findByText("View Surrogates")).toBeVisible()
        expect(within(roleSection).queryByText("Send Email")).not.toBeInTheDocument()
        fireEvent.click(await screen.findByRole("button", { name: "Add permission" }))
        expect(screen.queryByRole("combobox", { name: "Override type" })).not.toBeInTheDocument()
        choose("Permission", "View Reports")
        expect(screen.queryByRole("option", { name: "Manage Roles" })).not.toBeInTheDocument()
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Add permission" }))
        await waitFor(() => expect(api.updateMember).toHaveBeenCalledWith("member-1", { add_overrides: [{ permission: "view_reports", override_type: "grant" }] }))
    })

    it("requires explicit carry decisions when changing a returning inactive member’s role", async () => {
        vi.mocked(api.getMember).mockResolvedValue({ ...member, is_active: false })
        render(<PermissionMemberDetail memberId="member-1" />)
        expect(await screen.findByText("Inactive")).toBeVisible()
        await waitFor(() => expect(screen.getByRole("combobox", { name: "Role" })).toHaveTextContent("Case Manager"))
        choose("Role", "Operations")
        fireEvent.click(screen.getByRole("button", { name: "Review role change" }))
        const apply = await screen.findByRole("button", { name: "Apply role change" })
        expect(apply).toBeDisabled()
        await screen.findByRole("combobox", { name: "Action and scope additions (2)" })
        choose("Action and scope additions (2)", "Keep existing additions")
        expect(apply).toBeDisabled()
        choose("Record collaborations (1)", "Remove existing collaborations")
        expect(apply).toBeEnabled()
        expect(screen.getByText("Record scope changes")).toBeVisible()
        expect(screen.getByRole("dialog")).toHaveTextContent("Assigned records · After approval")
        expect(screen.getByRole("dialog")).toHaveTextContent("All records · All phases")
        fireEvent.click(apply)
        await waitFor(() => expect(api.updateMember).toHaveBeenCalledWith("member-1", { role: "operations", access_reviewed: true, retain_additions: true, retain_collaborators: false }))
    })

    it("keeps a rejected role review open with the selected decisions", async () => {
        vi.mocked(api.updateMember).mockRejectedValue(new Error("Role change denied"))
        render(<PermissionMemberDetail memberId="member-1" />)
        await screen.findByRole("combobox", { name: "Role" })
        choose("Role", "Operations")
        fireEvent.click(screen.getByRole("button", { name: "Review role change" }))
        await screen.findByRole("combobox", { name: "Action and scope additions (2)" })
        choose("Action and scope additions (2)", "Remove existing additions")
        choose("Record collaborations (1)", "Keep existing collaborations")
        fireEvent.click(screen.getByRole("button", { name: "Apply role change" }))
        expect(await screen.findByRole("alert")).toHaveTextContent("Role change denied")
        expect(screen.getByRole("dialog")).toBeVisible()
        expect(screen.getByRole("combobox", { name: "Record collaborations (1)" })).toHaveTextContent("Keep existing collaborations")
    })

    it("honors server edit capabilities for the current user", async () => {
        vi.mocked(api.getMember).mockResolvedValue({ ...member, user_id: "admin-user", capabilities: { can_manage_members: false, can_add_permissions: false } })
        render(<PermissionMemberDetail memberId="member-1" />)
        expect(await screen.findByText("You")).toBeVisible()
        expect(screen.getByRole("combobox", { name: "Role" })).toBeDisabled()
        expect(screen.queryByRole("button", { name: "Add permission" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Remove member" })).not.toBeInTheDocument()
    })

    it("shows a retryable member load error", async () => {
        vi.mocked(api.getMember).mockRejectedValue(new Error("Member could not be loaded"))
        render(<PermissionMemberDetail memberId="member-1" />)
        expect(await screen.findByRole("alert")).toHaveTextContent("Member could not be loaded")
        expect(screen.getByRole("button", { name: "Try again" })).toBeVisible()
    })
    it("shows defaults only in the preview and excludes stale default additions from role carryover", async () => {
        const defaultKey = "use_ai_assistant"
        vi.mocked(api.getMember).mockResolvedValue({ ...member, effective_permissions: [...member.effective_permissions, defaultKey], overrides: [...member.overrides, { permission: defaultKey, label: "Use AI Assistant", category: "AI", override_type: "grant" }], included_features: { personal_workspace: true, ai_assistant: false }, access_sources: { ...member.access_sources, [defaultKey]: ["included_feature"] } })
        vi.mocked(api.getAvailablePermissions).mockResolvedValue([{ key: defaultKey, label: "Use AI Assistant", category: "AI", description: "", developer_only: false, is_default: true, assignable: true }, { key: "manage_automation", label: "Manage Personal Workflows", category: "Workflows", description: "", developer_only: false, is_default: true, assignable: true }, { key: "view_reports", label: "View Reports", category: "Reports", description: "", developer_only: false, assignable: true }])
        render(<PermissionMemberDetail memberId="member-1" />)
        expect(await screen.findByText("Personal workspace")).toBeVisible()
        expect(screen.getByText("AI Assistant")).toBeVisible()
        expect(screen.getByText("Disabled")).toBeVisible()
        expect(screen.queryByRole("button", { name: "Remove Use AI Assistant addition" })).not.toBeInTheDocument()
        fireEvent.click(await screen.findByRole("button", { name: "Add permission" }))
        fireEvent.click(screen.getByRole("combobox", { name: "Permission" }))
        expect(screen.getByRole("option", { name: "View Reports" })).toBeInTheDocument()
        expect(screen.queryByRole("option", { name: "Manage Personal Workflows" })).not.toBeInTheDocument()
        fireEvent.keyDown(screen.getByRole("listbox"), { key: "Escape" })
        fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
        choose("Role", "Operations")
        fireEvent.click(screen.getByRole("button", { name: "Review role change" }))
        await screen.findByRole("combobox", { name: "Action and scope additions (2)" })
        expect(screen.getByRole("dialog")).not.toHaveTextContent("Use AI Assistant")
    })

})
